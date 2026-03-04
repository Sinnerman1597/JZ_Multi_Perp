import yaml
import asyncio
from telethon import TelegramClient, events

async def main():
    print("=== 原生 TG 無底線監聽測試 ===")
    
    # 讀取剛剛的 Jimmy_session
    with open("config.yaml", "r", encoding="utf-8") as f:
        tg_cfg = yaml.safe_load(f).get('signals', {}).get('telegram_config', {})
    
    client = TelegramClient(tg_cfg.get('session_name'), tg_cfg.get('api_id'), tg_cfg.get('api_hash'))
    await client.start()
    print("✔ 連線成功！現在您用手機傳送隨便一個訊息給任何群組這隻程式都會印出來。請等待報單群組發言...")
    
    # 這裡【不使用】 chats=... 來限制，而是全部攔截
    @client.on(events.NewMessage())
    async def handler(event):
        # 印出真實的 Chat ID 和訊息內容
        chat_id = event.chat_id
        text = event.message.message or "[空白或圖片]"
        print(f"收到來自真實 Chat ID: {chat_id} 的訊息 -> {text}")

    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
