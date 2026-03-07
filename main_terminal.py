import sys
import os
import asyncio
from datetime import datetime

# 解決路徑問題
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.cli.cli_controller import CLIController
from rich.console import Console

console = Console()

class TerminalController(CLIController):
    """
    修改自 CLIController，在終端機直接印出文字日誌而非使用 Dashboard UI，
    方便除錯與觀察。
    """
    async def _start_monitoring_session(self, exchange_id):
        from src.infrastructure.signal_receivers.tg_receiver import TGSignalReceiver
        
        self.engine.is_running = True
        
        # --- 覆寫 (Monkey Patch) Engine 的 process_incoming_message ---
        # 以便能在收到訊息時第一時間在終端機上印出收到的訊號
        original_process = self.engine.process_incoming_message
        
        def terminal_process(source_name, raw_message):
            now_time = datetime.now().strftime("%H:%M:%S")
            # 移除換行符避免訊號佔據太多行
            clean_msg = str(raw_message).replace('\n', ' ')
            console.print(f"[dim][{now_time}] [TG 訊號] 從頻道 {source_name} 收到訊息：{clean_msg}[/dim]")
            
            # 繼續原本的解析與分派流程
            original_process(source_name, raw_message)
            
        self.engine.process_incoming_message = terminal_process
        
        # --- 1. 啟動連線預檢 ---
        sig_cfg = self.selected_signal_config if self.selected_signal_config else self.config.get('signals', {})
        receiver = TGSignalReceiver(self.engine, sig_cfg)
        
        try:
            console.print("\n[bold yellow]📡 正在連接 Telegram... (全終端機純文字模式)[/bold yellow]")
            await receiver.connect_and_auth()
            console.print("[bold green]✔ 連線與授權成功！開始全時段監控並印出收到的訊號...[/bold green]")
            console.print("[dim]提示: 每 30 秒將會自動印出目前持倉狀態，以便觀察運行狀況。[/dim]\n")
        except Exception as e:
            console.print(f"[bold red]❌ Telegram 初始化失敗: {e}[/bold red]")
            return

        # 啟動非同步接收任務
        receiver_task = asyncio.create_task(receiver.run_forever())
        
        # 2. 監控主迴圈 (定期列印持倉與簡單心跳)
        try:
            loop_count = 0
            while self.engine.is_running:
                await asyncio.sleep(5)
                loop_count += 5
                
                # 每 30 秒印一次持倉狀態 (僅在有持倉時顯示)
                if loop_count >= 30:
                    loop_count = 0
                    active_trades = self.engine.stats.get('active_trades', [])
                    now_time = datetime.now().strftime("%H:%M:%S")
                    
                    if active_trades:
                        console.print(f"\n[bold cyan]=== [{now_time}] 目前持倉狀態 ({len(active_trades)} 筆) ===[/bold cyan]")
                        for trade in active_trades:
                            symbol = trade.get('symbol', 'N/A')
                            side = trade.get('side', 'N/A')
                            entry = float(trade.get('entry_price', 0))
                            amount = trade.get('remaining_amount', 'N/A')
                            stage = trade.get('current_tp_stage', 0)
                            ex = trade.get('exchange')
                            exchange_name = ex.exchange_id if ex else 'N/A'
                            
                            # 獲取現價與計算盈虧
                            current_price = "N/A"
                            pnl_str = ""
                            if ex:
                                try:
                                    ticker = ex.get_ticker(symbol)
                                    cur = float(ticker['last'])
                                    current_price = f"{cur}"
                                    if entry > 0:
                                        pnl = ((cur - entry) / entry * 100) if side == 'buy' else ((entry - cur) / entry * 100)
                                        pnl_color = "green" if pnl >= 0 else "red"
                                        pnl_str = f" | [bold {pnl_color}]PnL: {pnl:+.2f}%[/bold {pnl_color}]"
                                except: pass

                            side_colored = f"[bold green]{side.upper()}[/bold green]" if side == 'buy' else f"[bold red]{side.upper()}[/bold red]"
                            console.print(f" ► [[bold yellow]{exchange_name.upper()}[/bold yellow]] [bold]{symbol}[/bold] | {side_colored} | 階: {stage} | 入場: {entry} | [bold white]現價: {current_price}[/bold white]{pnl_str} | 量: {amount}")
                        console.print("[bold cyan]==============================================[/bold cyan]\n")
                    
        except asyncio.CancelledError:
            pass # 處理 Ctrl+C 結束信號
        except Exception as e:
            console.print(f"[red]監控主迴圈發生錯誤: {e}[/red]")
        finally:
            # 關閉流程
            self.engine.is_running = False
            await self.engine.stop()
            await receiver.stop()
            if not receiver_task.done():
                receiver_task.cancel()
                try: await receiver_task
                except: pass
            console.print("[yellow]系統已安全關閉。[/yellow]")

# 修正 Windows 平台上 ProactorEventLoop 關閉時的 bug (Telethon 需要)
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def main():
    try:
        controller = TerminalController()
        # 啟動非同步選單，與主程式流程一致，只有實作監控階段不同
        await controller.run_menu()
    except KeyboardInterrupt:
        print("\n使用者停止程式。")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n[Fatal Error] 系統發生致命錯誤: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
