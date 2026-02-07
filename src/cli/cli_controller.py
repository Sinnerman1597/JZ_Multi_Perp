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

    def run_menu(self):
        console.print("[bold blue]=== 交易系統啟動選單 ===[/bold blue]\n")

        # 1. 選擇交易所
        exchange_options = list(self.config.get('exchange', {}).keys())
        if 'active' in exchange_options: exchange_options.remove('active')
        
        exchange_id = questionary.select(
            "請選擇要執行的交易所:",
            choices=exchange_options
        ).ask()

        # 2. 初始化引擎
        exchange_cfg = self.config.get('exchange')
        exchange_cfg['active'] = exchange_id # 覆寫為使用者選定的
        exchange = ExchangeManager.create_exchange(exchange_cfg)
        self.engine = StrategyEngine(exchange)

        # 3. 選擇執行模式
        mode = questionary.select(
            "請選擇執行模式:",
            choices=[
                "1. 自主指標策略 (Self-Managed)",
                "2. 外部訊號跟單 (Signal-Driven)",
                "3. 混合模式 (兩者並行)"
            ]
        ).ask()

        # 4. 根據模式配置內容
        if "1" in mode or "3" in mode:
            self._setup_strategy_flow(exchange)
        
        if "2" in mode or "3" in mode:
            self._setup_signals_flow()

        # 5. 最後確認並啟動
        confirm = questionary.confirm("配置完成，是否啟動交易引擎?").ask()
        if confirm:
            self._start_monitoring_session(exchange_id)

    def _start_monitoring_session(self, exchange_id):
        from rich.live import Live
        from src.ui.dashboard import Dashboard
        import time

        self.engine.is_running = True
        layout = Dashboard.create_layout()
        
        console.print("\n[bold green]✔ 引擎已成功在背景啟動。[/bold green]")
        
        with Live(layout, refresh_per_second=4, screen=False) as live:
            while self.engine.is_running:
                # 1. 更新 UI 數據
                layout["header"].update(Dashboard.get_header_panel())
                layout["main"].update(Dashboard.get_stats_panel(self.engine.stats, exchange_id))
                layout["footer"].update(Dashboard.get_footer_panel())
                
                # 2. 模擬監控狀態 (在實際開發中，這裡會是異步等待訊號)
                # 為了讓使用者能輸入指令，我們採用非阻塞式模擬
                time.sleep(0.5)

                # 3. 獲取使用者輸入 (簡易版指令處理)
                # 注意：在正式環境建議使用 aioconsole 或 threading 處理輸入，避免阻塞 UI
                # 這裡先實作一個能讓使用者跳出的邏輯
                if not self.engine.is_running:
                    break

        # 退出後的處理
        console.print("[yellow]引擎已安全停止。[/yellow]")

    def _setup_strategy_flow(self, exchange):
        strategy_name = questionary.select(
            "請選擇交易策略:",
            choices=StrategyFactory.get_available_strategies()
        ).ask()

        strategy = StrategyFactory.create_strategy(strategy_name, exchange)
        
        # 動態參數配置 (上下文感知)
        console.print(f"\n[bold yellow]配置策略參數: {strategy_name}[/bold yellow]")
        final_params = {}
        for param_id, info in strategy.requirements.items():
            desc = f"{info['description']} (預設: {info.get('default')})"
            val = questionary.text(desc).ask()
            
            # 若沒輸入則用預設值，並處理型性轉換
            if val == "":
                final_params[param_id] = info.get('default')
            else:
                target_type = info.get('type', 'string')
                final_params[param_id] = int(val) if target_type == 'int' else val

        self.engine.add_strategy(strategy, final_params)

    def _setup_signals_flow(self):
        # 讀取 config.yaml 中的訊號源
        signal_cfg = self.config.get('signals')
        if not signal_cfg or not signal_cfg.get('enabled'):
            console.print("[red]⚠ 警告: YAML 中尚未啟用訊號源或配置為停用[/red]")
        
        self.engine.setup_signal_sources(signal_cfg)
        console.print("[green]✔ 已完成訊號監聽源加載[/green]")
