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
        confirm = await questionary.confirm("配置完成，是否啟動交易引擎?").ask_async()
        if confirm:
            await self._start_monitoring_session(exchange_id)

    async def _start_monitoring_session(self, exchange_id):
        from rich.live import Live
        from src.ui.dashboard import Dashboard
        from src.infrastructure.signal_receivers.tg_receiver import TGSignalReceiver
        import asyncio

        self.engine.is_running = True
        layout = Dashboard.create_layout()
        
        console.print("\n[bold green]✔ 引擎與監聽任務準備啟動...[/bold green]")
        
        # 初始化並啟動 Telegram 接收器 (非同步任務)
        receiver = TGSignalReceiver(self.engine, self.config.get('signals', {}))
        receiver_task = asyncio.create_task(receiver.start())

        try:
            with Live(layout, refresh_per_second=4, screen=False) as live:
                while self.engine.is_running:
                    # 1. 更新 UI 數據
                    layout["header"].update(Dashboard.get_header_panel())
                    layout["main"].update(Dashboard.get_stats_panel(self.engine.stats, exchange_id))
                    layout["footer"].update(Dashboard.get_footer_panel())
                    
                    # 2. 異步等待，不阻塞事件循環
                    await asyncio.sleep(0.5)

                    if not self.engine.is_running:
                        break
        except Exception as e:
            console.print(f"[red]監控過程發生錯誤: {e}[/red]")
        finally:
            self.engine.is_running = False
            await receiver.stop()
            receiver_task.cancel()
            console.print("[yellow]引擎已安全停止。[/yellow]")

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
