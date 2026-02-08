import questionary
from rich.console import Console
from typing import Dict, Any

from src.infrastructure.config_loader import ConfigLoader
from src.core.exchange_manager import ExchangeManager
from src.core.strategy_factory import StrategyFactory
from src.core.strategy_engine import StrategyEngine

console = Console()

class CLIController:
    """控制中心：處理互動選單與啟動流程"""

    def __init__(self):
        self.engine = None
        self.config = ConfigLoader.load_config()

    async def run_menu(self):
        console.print("[bold blue]=== 交易系統啟動選單 ===[/bold blue]\n")

        # 1. 選擇交易所
        exchange_cfg = self.config.get('exchange', {})
        exchange_options = list(exchange_cfg.keys())
        if 'active' in exchange_options: exchange_options.remove('active')
        
        active_default = exchange_cfg.get('active', '').lower()
        default_choice = None
        for opt in exchange_options:
            if opt.lower() == active_default:
                default_choice = opt
                break
        
        exchange_id = await questionary.select(
            "請選擇要執行的交易所:",
            choices=exchange_options,
            default=default_choice
        ).ask_async()

        # 2. 初始化引擎
        exchange_cfg = self.config.get('exchange')
        exchange_cfg['active'] = exchange_id 
        exchange = ExchangeManager.create_exchange(exchange_cfg)
        self.engine = StrategyEngine(exchange)

        # 3. 選擇執行模式
        mode = await questionary.select(
            "請選擇執行模式:",
            choices=[
                "1. 自主指標策略 (Self-Managed)",
                "2. 外部訊號跟單 (Signal-Driven)",
                "3. 混合模式 (兩者並行)"
            ]
        ).ask_async()

        # 4. 根據模式配置內容
        if "1" in mode or "3" in mode:
            await self._setup_strategy_flow(exchange)
        
        if "2" in mode or "3" in mode:
            self._setup_signals_flow()

        # 5. 最後確認並啟動
        confirm_choice = await questionary.select(
            "配置完成，是否啟動交易引擎?",
            choices=[
                "Yes (啟動)",
                "No (結束程式)"
            ],
            default="Yes (啟動)"
        ).ask_async()

        if confirm_choice == "Yes (啟動)":
            await self._start_monitoring_session(exchange_id)

    async def _start_monitoring_session(self, exchange_id):
        from rich.live import Live
        from src.ui.dashboard import Dashboard
        from src.infrastructure.signal_receivers.tg_receiver import TGSignalReceiver
        import asyncio

        self.engine.is_running = True
        layout = Dashboard.create_layout()
        
        # --- 1. 啟動連線預檢 (包含互動式登入) ---
        receiver = TGSignalReceiver(self.engine, self.config.get('signals', {}))
        
        try:
            console.print("\n[bold yellow]📡 正在連接 Telegram... (若為第一次登入，請依提示輸入資訊)[/bold yellow]")
            await receiver.connect_and_auth()
            console.print("[bold green]✔ 連線與授權成功！正在開啟監控面板...[/bold green]")
            await asyncio.sleep(1) # 給使用者看一眼成功訊息
        except Exception as e:
            console.print(f"[bold red]❌ Telegram 初始化失敗: {e}[/bold red]")
            return

        # 啟動非同步運行任務 (在背景跑 run_forever)
        receiver_task = asyncio.create_task(receiver.run_forever())
        
        # 2. 啟動非同步指令監聽 (stop/test)
        input_queue = asyncio.Queue()
        async def _read_input():
            while self.engine.is_running:
                cmd = await asyncio.get_event_loop().run_in_executor(None, input)
                await input_queue.put(cmd.strip().lower())

        input_task = asyncio.create_task(_read_input())

        try:
            with Live(layout, refresh_per_second=4, screen=False) as live:
                while self.engine.is_running:
                    # 處理待處理的指令
                    while not input_queue.empty():
                        cmd = await input_queue.get()
                        if cmd == 'stop':
                            self.engine.is_running = False
                        elif cmd == 'test':
                            self._trigger_mock_signal()
                    
                    # 更新 UI
                    layout["header"].update(Dashboard.get_header_panel())
                    layout["upper"].update(Dashboard.get_stats_panel(self.engine.stats, exchange_id))
                    layout["middle"].update(Dashboard.get_trades_panel(self.engine.stats['active_trades']))
                    layout["lower"].update(Dashboard.get_logs_panel(self.engine.stats['message_logs']))
                    layout["footer"].update(Dashboard.get_footer_panel())
                    
                    await asyncio.sleep(0.5)

                    if not self.engine.is_running:
                        break
        except Exception as e:
            console.print(f"[red]監控過程發生錯誤: {e}[/red]")
        finally:
            self.engine.is_running = False
            await receiver.stop()
            receiver_task.cancel()
            input_task.cancel()
            console.print("[yellow]引擎已安全停止。[/yellow]")

    def _trigger_mock_signal(self):
        """模擬一則 AdTrack 測試訊號"""
        mock_msg = (
            "📈 交易對：TESTUSDT\n"
            "📊 倉位：LONG\n"
            "💪 槓桿倍數：10X\n"
            "🔍 進場區域：1.0-2.0\n"
            "⛔ 止損：0.5\n"
            "🎯 目標1：3.0\n"
            "🎯 目標2：4.0"
        )
        print("\n[Test Mode] 正在模擬推送測試訊號...")
        # 尋找具備 adtrack_parser 的來源名稱並推送
        source_name = next(iter(self.engine.parsers.keys()), "Test_Source")
        self.engine.process_incoming_message(source_name, mock_msg)

    async def _setup_strategy_flow(self, exchange):
        strategy_name = await questionary.select(
            "請選擇交易策略:",
            choices=StrategyFactory.get_available_strategies()
        ).ask_async()

        strategy = StrategyFactory.create_strategy(strategy_name, exchange)
        
        console.print(f"\n[bold yellow]配置策略參數: {strategy_name}[/bold yellow]")
        final_params = {}
        for param_id, info in strategy.requirements.items():
            desc = f"{info['description']} (預設: {info.get('default')})"
            val = await questionary.text(desc).ask_async()
            
            if val == "":
                final_params[param_id] = info.get('default')
            else:
                target_type = info.get('type', 'string')
                final_params[param_id] = int(val) if target_type == 'int' else val

        self.engine.add_strategy(strategy, final_params)

    def _setup_signals_flow(self):
        signal_cfg = self.config.get('signals')
        if not signal_cfg or not signal_cfg.get('enabled'):
            console.print("[red]⚠ 警告: YAML 中尚未啟用訊號源或配置為停用[/red]")
        
        self.engine.setup_signal_sources(signal_cfg)
        console.print("[green]✔ 已完成訊號解析器註冊[/green]")
