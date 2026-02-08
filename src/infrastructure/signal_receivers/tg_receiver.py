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
                self.channel_map[entity.id] = name
                print(f"[TG Receiver] ✔ 成功解析頻道: {name} (ID: {entity.id})")
            except Exception as e:
                print(f"[TG Receiver] ❌ 無法解析頻道 '{name}' ({cid}): {e}")
        
        if not valid_entities:
            raise ValueError("未找到任何有效的監控頻道，請檢查 config.yaml")

        self._register_handlers(valid_entities)
        return True

    def _register_handlers(self, valid_entities):
        """註冊訊息攔截規則"""
        @self.client.on(events.NewMessage(chats=valid_entities))
        async def handler(event):
            source_name = self.channel_map.get(event.chat_id)
            if not source_name: return

            raw_text = event.message.message or ""
            
            # --- 超精確過濾：必須同時包含『預言機』與『交易對』關鍵欄位 ---
            if "預言機" in raw_text and "交易對" in raw_text:
                # 只有符合格式的才推送給引擎
                self.engine.process_incoming_message(source_name, raw_text)
            else:
                # 忽略其他 Topic 的訊息
                pass

    async def run_forever(self):
        """第二階段：開始無限期監聽"""
        if not self.client: return
        self._is_running = True
        self.engine.stats['status'] = "🟢 Telegram 監聽中..."
        
        try:
            await self.client.run_until_disconnected()
        except Exception as e:
            # 捕獲 TypeNotFoundError (Constructor ID 錯誤) 等 Telethon 解析異常
            if "Constructor ID" in str(e):
                console.print("[yellow][TG Receiver] 收到不支援的更新格式 (TypeNotFoundError)，已忽略並繼續監聽。[/yellow]")
                # 重新運行直至正式斷開
                await self.run_forever()
            elif self._is_running:
                console.print(f"[red][TG Receiver] 監聽中斷: {e}[/red]")
        
        self.engine.stats['status'] = "⚪ Telegram 已斷開"

    async def stop(self):
        """停止接收器"""
        if self.client:
            await self.client.disconnect()
            self._is_running = False
            print("[TG Receiver] Telegram 已離線")
