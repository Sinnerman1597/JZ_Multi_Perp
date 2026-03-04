from telethon import TelegramClient, events
import asyncio
from typing import Dict, Any
from rich.console import Console

console = Console()

class TGSignalReceiver:
    """Telegram 訊號接收器 (使用 Telethon)"""

    def __init__(self, engine, config: Dict[str, Any]):
        self.engine = engine
        self.config = config
        self.client = None
        self._is_running = False
        self.channel_map = {}

    async def connect_and_auth(self):
        """第一階段：建立連線並處理互動式驗證"""
        # 修正：改從 telegram_config 子層級讀取
        tg_cfg = self.config.get('telegram_config', {})
        session_name = tg_cfg.get('session_name', 'trade_bot')
        api_id = tg_cfg.get('api_id')
        api_hash = tg_cfg.get('api_hash')

        if not api_id or not api_hash:
            raise ValueError("缺少 API_ID 或 API_HASH 設定")

        # 初始化客戶端
        self.client = TelegramClient(session_name, api_id, api_hash)
        
        # 執行互動式登入 (如果需要，會在此處提示輸入電話、驗證碼)
        await self.client.start()
        
        # 檢查頻道權限
        print("[TG Receiver] 正在檢查頻道權限...")
        sources = self.config.get('sources', [])
        tg_sources = [s for s in sources if s.get('type') == 'telegram']
        
        valid_entities = []
        self.channel_map = {}
        
        for s in tg_sources:
            cid = s.get('channel_id')
            name = s.get('name')
            try:
                entity = await self.client.get_entity(cid)
                valid_entities.append(entity)
                
                # --- 強大對照表：同時存入多種可能的 ID 格式 ---
                raw_id = entity.id
                prefixed_id = int(f"-100{raw_id}") if not str(raw_id).startswith('100') else int(f"-{raw_id}")
                
                self.channel_map[raw_id] = name
                self.channel_map[prefixed_id] = name
                self.channel_map[str(raw_id)] = name
                self.channel_map[str(prefixed_id)] = name
                
                print(f"[TG Receiver] ✔ 成功解析頻道: {name} (原始ID: {raw_id} | 匹配ID: {prefixed_id})")
            except Exception as e:
                print(f"[TG Receiver] ❌ 無法解析頻道 '{name}' ({cid}): {e}")
        
        if not valid_entities:
            raise ValueError("未找到任何有效的監控頻道，請檢查 config.yaml")

        self._register_handlers(valid_entities)
        return True

    def _register_handlers(self, valid_entities):
        """註冊訊息攔截規則"""
        # 暫時解除 chats 綁定限制，改用全局攔截 + 內部對照表過濾 (這樣最穩，保證能收到訊號)
        @self.client.on(events.NewMessage()) 
        async def handler(event):
            # 取得當前訊息的來源 ID (可能是正數、可能是負數)
            chat_id = event.chat_id
            source_name = self.channel_map.get(chat_id) or self.channel_map.get(str(chat_id))
            
            # 如果不是我們要監聽的頻道，直接靜默退出
            if not source_name:
                return

            current_text = event.message.message or ""
            processed_text = current_text
            
            # --- 精確回覆處理：僅平倉指令需要回溯上下文 ---
            is_closing_single = "closing here" in current_text.lower()
            if is_closing_single and event.is_reply:
                reply_msg = await event.get_reply_message()
                if reply_msg and reply_msg.message:
                    # 僅在此時合併上下文，防止進場訊號被回覆觸發重複執行
                    processed_text = f"{current_text} [REPLY_TO] {reply_msg.message}"

            # --- 取消硬性白名單，將所有來自頻道的訊息無條件送交引擎，交由各策略專屬解析器(Parser)自行判斷格式 ---
            self.engine.process_incoming_message(source_name, processed_text)

    async def run_forever(self):
        """第二階段：主動式自動重連監聽"""
        if not self.client: return
        self._is_running = True
        retry_delay = 5  # 初始重連等待秒數

        while self._is_running:
            try:
                # 1. 檢查並建立物理連線
                if not self.client.is_connected():
                    self.engine.stats['status'] = "🟡 正在連線 Telegram..."
                    await self.client.connect()
                
                # 2. 啟動監聽程序
                self.engine.stats['status'] = "🟢 Telegram 監聽中..."
                console.print("[green][TG Receiver] 監聽程序啟動成功。[/green]")
                
                # 將重連等待重置
                retry_delay = 5
                
                # run_until_disconnected 會阻塞直到斷線
                # 這裡可能拋出 TypeNotFoundError，我們需要將其視為可忽略的更新
                try:
                    await self.client.run_until_disconnected()
                except TypeError as te:
                     if "Constructor ID" in str(te):
                         console.print("[dim][TG Receiver] 忽略未知的 Constructor ID 更新包[/dim]")
                         # 由於 run_until_disconnected 退出，直接進行下一次 loop 恢復連線
                         continue
                     else:
                         raise te
                
            except Exception as e:
                if not self._is_running: break
                
                # 處理 Telethon 特有的解析異常 (Constructor ID, 內部時戳過期)
                # 有些版本拋出的是 ValueError 或 TypeNotFoundError 或 PersistentTimestampOutdatedError
                err_str = str(e)
                if "Constructor ID" in err_str or "TypeNotFoundError" in err_str or "PersistentTimestampOutdatedError" in err_str or "Persistent timestamp outdated" in err_str:
                    console.print(f"[yellow][TG Receiver] 收到不支援的更新內容或時戳過期，嘗試忽略並重置連線 ({err_str[:80]}...)[/yellow]")
                    await asyncio.sleep(1) # 短暫等待後立即重試
                    continue
                else:
                    console.print(f"[red][TG Receiver] 監聽異常中斷: {e}[/red]")
                
                # 4. 異常重連邏輯
                self.engine.stats['status'] = f"🔴 Telegram 斷線 ({retry_delay}s 後重連)"
                await asyncio.sleep(retry_delay)
                
                # 稍微增加重連等待，避免網路極差時頻繁衝擊伺服器 (最大 60秒)
                retry_delay = min(retry_delay + 5, 60)
        
        self.engine.stats['status'] = "⚪ Telegram 已停止"

    async def stop(self):
        """停止接收器"""
        if self.client:
            await self.client.disconnect()
            self._is_running = False
            print("[TG Receiver] Telegram 已離線")
