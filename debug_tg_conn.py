import yaml
import asyncio
import traceback
from telethon import TelegramClient

async def debug_telegram():
    print("=== JZ_Multi_Perp Telegram 連線測試與訊息驗證工具 (Topic 過濾版) ===")
    
    # 1. 讀取配置
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        tg_cfg = config.get('signals', {}).get('telegram_config', {})
        api_id = tg_cfg.get('api_id')
        api_hash = tg_cfg.get('api_hash')
        session_name = tg_cfg.get('session_name', 'trade_bot')
        
        sources = config.get('signals', {}).get('sources', [])
        tg_sources = [s for s in sources if s.get('type') == 'telegram']

        print(f"[Step 1] 配置讀取成功")
        print(f" - API_ID: {api_id}")
        print(f" - API_HASH: {api_hash[:5]}***")
        print(f" - Session Name: {session_name}")
        print(f" - 待測試頻道數: {len(tg_sources)}")
    except Exception as e:
        print(f"[Step 1] ❌ 讀取 config.yaml 失敗:")
        traceback.print_exc()
        return

    # 2. 測試連線與授權
    print(f"\n[Step 2] 正在嘗試連接 Telegram 伺服器...")
    client = TelegramClient(session_name, api_id, api_hash)
    try:
        await client.connect()
        print(f" - 網路連接: 成功")
        
        is_auth = await client.is_user_authorized()
        if is_auth:
            print(f" - 帳號授權狀態: 🟢 已授權 (Session 有效)")
        else:
            print(f" - 帳號授權狀態: 🔴 未授權 (Session 無效或檔案不正確)")
            print("   請注意：如果是第一次使用，請先執行 main.py 完成登入流程。")
            await client.disconnect()
            return

    except Exception as e:
        print(f"[Step 2] ❌ Telegram 連線或授權檢查發生錯誤:")
        traceback.print_exc()
        await client.disconnect()
        return

    # 3. 測試頻道權限與獲取最新訊息 (加入 Topic 過濾)
    print(f"\n[Step 3] 正在檢查頻道權限並獲取『合約預言機』最新訊息...")
    for s in tg_sources:
        cid = s.get('channel_id')
        name = s.get('name')
        print(f"\n>> 正在解析頻道 '{name}' (ID: {cid})...")
        try:
            # 解析頻道 ID
            try: target = int(cid)
            except: target = cid
            
            entity = await client.get_entity(target)
            print(f"   🟢 解析成功! (實際 ID: {entity.id})")
            
            # 獲取訊息並過濾關鍵字 (移除 50 則限制，持續搜尋直到滿 5 則)
            print(f"   📥 正在向後遍歷歷史訊息，直到滿足 5 則標竿訊號...")
            found_count = 0
            
            # 使用 limit=None 進行全量遍歷，直到 break
            async for msg in client.iter_messages(entity, limit=None):
                text = msg.message or ""
                # 同步主程式邏輯：必須同時包含 預言機 與 交易對
                if "預言機" in text and "交易對" in text:
                    found_count += 1
                    clean_text = text.replace('\n', ' ')
                    if len(clean_text) > 80:
                        clean_text = clean_text[:80] + "..."
                    print(f"      {found_count}. [{msg.date.strftime('%Y-%m-%d %H:%M:%S')}] {clean_text}")
                    
                    if found_count >= 5:
                        break
            
            if found_count == 0:
                print("      [⚠️ 錯誤] 搜尋了大量歷史訊息，仍找不到符合『預言機』+『交易對』的內容。")
                print("      請檢查關鍵字是否完全匹配（例如：是『預言機』還是『預言磯』？）。")

        except Exception as e:
            print(f"   ❌ 失敗!")
            print(f"   原因: {e}")

    await client.disconnect()
    print("\n=== 測試完成 ===")

if __name__ == "__main__":
    asyncio.run(debug_telegram())
