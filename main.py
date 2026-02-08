import sys
import os
import asyncio

# 解決路徑問題
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.cli.cli_controller import CLIController

# 修正 Windows 平台上 ProactorEventLoop 關閉時的 bug
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def main():
    try:
        controller = CLIController()
        # 啟動非同步選單
        await controller.run_menu()
    except KeyboardInterrupt:
        print("\n使用者停止程式。")
    except Exception as e:
        # 這裡會捕獲所有異常並顯示，方便除錯
        import traceback
        traceback.print_exc()
        print(f"\n[Fatal Error] 系統發生致命錯誤: {e}")

if __name__ == "__main__":
    # 使用 asyncio 啟動
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
