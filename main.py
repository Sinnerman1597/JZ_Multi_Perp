import sys
import os

# 解決路徑問題
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.cli.cli_controller import CLIController

def main():
    try:
        controller = CLIController()
        controller.run_menu()
    except KeyboardInterrupt:
        print("\n使用者停止程式。")
    except Exception as e:
        print(f"\n[Fatal Error] 系統發生致命錯誤: {e}")

if __name__ == "__main__":
    main()
