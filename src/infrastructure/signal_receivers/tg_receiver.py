import asyncio
from telethon import TelegramClient, events
from typing import Dict, Any, List
from src.core.strategy_engine import StrategyEngine

class TGSignalReceiver:
    """
    Telegram 訊號接收器。
    使用 Telethon 監聽特定頻道的訊息，並推送到 StrategyEngine。
    """

    def __init__(self, engine: StrategyEngine, config: Dict[str, Any]):
        self.engine = engine
        self.config = config
        self.client: TelegramClient = None
        self._is_running = False

    async def start(self):
        """啟動 Telegram 客戶端並開始監聽"""
        tg_cfg = self.config.get('telegram_config', {})
        api_id = tg_cfg.get('api_id')
        api_hash = tg_cfg.get('api_hash')
        session_name = tg_cfg.get('session_name', 'trade_bot')

        if not api_id or not api_hash:
            print("[TG Receiver] 錯誤: 缺少 API_ID 或 API_HASH 設定")
            return

        # 初始化客戶端 (會自動尋找本地的 .session 檔案)
        self.client = TelegramClient(session_name, api_id, api_hash)
        
        # 註冊事件處理器
        self._register_handlers()

        print(f"[TG Receiver] 正在連接 Telegram (Session: {session_name})...")
        try:
            await self.client.start()
            self.engine.stats['status'] = "Telegram 連線成功，監聽中..."
            print("[TG Receiver] Telegram 連線成功，監聽中...")
        except Exception as e:
            self.engine.stats['status'] = f"連線失敗: {str(e)}"
            print(f"[TG Receiver] 連線失敗: {e}")
            return
        
        self._is_running = True
        # 持續運行直到連線中斷
        await self.client.run_until_disconnected()
        self.engine.stats['status'] = "Telegram 連線已斷開"

    def _register_handlers(self):
        """註冊訊息攔截規則"""
        
        # 取得所有需要監控的 TG 頻道 ID
        sources = self.config.get('sources', [])
        tg_sources = [s for s in sources if s.get('type') == 'telegram']
        
        # 建立頻道對應表 {channel_id: source_name}
        # 支援直接使用頻道 ID 或用戶名 (e.g., '@channel' 或 1234567)
        channel_map = {s.get('channel_id'): s.get('name') for s in tg_sources}
        watched_entities = list(channel_map.keys())

        @self.client.on(events.NewMessage(chats=watched_entities))
        async def handler(event):
            # 找到對應的 source_name
            # Telethon 的 event.chat_id 可能與輸入格式不同，需做匹配
            chat = await event.get_chat()
            
            # 嘗試匹配 username 或 ID
            source_name = None
            for cid, name in channel_map.items():
                if str(cid).replace('@', '') == getattr(chat, 'username', '') or str(cid) == str(event.chat_id):
                    source_name = name
                    break
            
            if source_name:
                raw_text = event.message.message
                print(f"[TG Receiver] 收到來自 {source_name} 的訊息")
                # 推送給引擎處理
                self.engine.process_incoming_message(source_name, raw_text)

    async def stop(self):
        """停止接收器"""
        if self.client:
            await self.client.disconnect()
            self._is_running = False
            print("[TG Receiver] Telegram 已離線")
