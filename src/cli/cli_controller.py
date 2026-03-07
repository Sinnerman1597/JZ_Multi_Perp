import questionary
from questionary import Style
from rich.console import Console
from typing import Dict, Any, List

# 定義自定義樣式，解決高亮塊不跟隨的問題並提升質感
custom_style = Style([
    ('qmark', 'fg:#ffffff bold'),       # 問題標誌顏色 (白色)
    ('question', 'bold'),               # 問題文字
    ('answer', 'fg:#f44336 bold'),      # 回答文字 (已確認的答案)
    ('pointer', 'fg:#ffffff bold'),     # 指標符號顏色 (白色)
    ('highlighted', 'bg:#ffffff fg:#000000 bold'), # 「唯一個」白色方塊：白底黑字
    ('selected', 'fg:#ffffff'),         # 被選中但「非焦點」項：不帶背景，純文字白
    ('separator', 'fg:#cc5454'),        # 分隔線
    ('instruction', 'fg:#858585 italic'), # 操作說明
    ('text', ''),                       # 普通文字
    ('disabled', 'fg:#858585 italic')   # 禁用項目
])

console = Console()

from src.infrastructure.config_loader import ConfigLoader
from src.core.exchange_manager import ExchangeManager
from src.core.strategy_factory import StrategyFactory
from src.core.strategy_engine import StrategyEngine
from src.core.exchange_router import ExchangeRouter

class CLIController:
    """控制中心：處理互動選單與啟動流程"""

    def __init__(self):
        self.engine = None
        self.config = ConfigLoader.load_config()
        self.selected_signal_config = None

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
            default=default_choice,
            style=custom_style
        ).ask_async()

        # 2. 初始化引擎 (包含多交易所路由器)
        exchange_cfg = self.config.get('exchange')
        exchange_cfg['active'] = exchange_id 
        exchange = ExchangeManager.create_exchange(exchange_cfg)
        
        # 初始化路由器 (AdTrack 專用)
        router = ExchangeRouter(exchange_cfg)
        
        self.engine = StrategyEngine(exchange, router=router)

        # 3. 選擇執行模式
        mode = await questionary.select(
            "請選擇執行模式:",
            choices=[
                "Signal-Driven (訊號跟單監測模式)",
                "Autonomous (單次手動/自主策略執行)"
            ],
            style=custom_style
        ).ask_async()

        # 4. 根據模式配置內容
        if "Signal-Driven" in mode:
            await self._setup_signals_flow(exchange)
        elif "Autonomous" in mode:
            await self._setup_strategy_flow(exchange)

        # 配置完成後的最終確認
        confirm_choice = await questionary.select(
            "配置完成，是否啟動交易引擎?",
            choices=["Yes (啟動)", "No (結束程序)"],
            default="Yes (啟動)",
            style=custom_style
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
        sig_cfg = self.selected_signal_config if self.selected_signal_config else self.config.get('signals', {})
        receiver = TGSignalReceiver(self.engine, sig_cfg)
        
        try:
            console.print("\n[bold yellow]📡 正在連接 Telegram... (若為第一次登入，請依提示輸入資訊)[/bold yellow]")
            await receiver.connect_and_auth()
            console.print("[bold green]✔ 連線與授權成功！正在開啟監控面板...[/bold green]")
            
            # 正式啟動所有策略的背景任務 (方案 B 等動作推遲到這裡)
            await self.engine.start_all_strategies()
            
            await asyncio.sleep(1) # 給使用者看一眼成功訊息
        except Exception as e:
            console.print(f"[bold red]❌ Telegram 初始化失敗: {e}[/bold red]")
            return

        # 啟動非同步運行任務 (在背景跑 run_forever)
        receiver_task = asyncio.create_task(receiver.run_forever())
        
        # 2. 監控主迴圈
        try:
            with Live(layout, refresh_per_second=4, screen=False) as live:
                while self.engine.is_running:
                    # 更新 UI
                    layout["header"].update(Dashboard.get_header_panel())
                    layout["upper"].update(Dashboard.get_stats_panel(self.engine.stats, exchange_id))
                    layout["middle"].update(Dashboard.get_trades_panel(self.engine.stats['active_trades']))
                    layout["lower"].update(Dashboard.get_logs_panel(self.engine.stats['message_logs']))
                    
                    await asyncio.sleep(0.5)

        except asyncio.CancelledError:
            pass # 處理 Ctrl+C
        except Exception as e:
            console.print(f"[red]監控過程發生錯誤: {e}[/red]")
        finally:
            self.engine.is_running = False
            # 1. 停止策略任務 (防止 Task pending 警告)
            await self.engine.stop()
            # 2. 停止訊號接收器
            await receiver.stop()
            if not receiver_task.done():
                receiver_task.cancel()
                try: await receiver_task
                except: pass
            console.print("[yellow]交易引擎已關閉。[/yellow]")

    async def _setup_strategy_flow(self, exchange):
        strategy_name = await questionary.select(
            "請選擇要執行的策略類型:",
            choices=list(StrategyFactory._REGISTERED_STRATEGIES.keys()),
            style=custom_style
        ).ask_async()

        strategy = StrategyFactory.create_strategy(strategy_name, exchange)
        
        console.print(f"\n[bold yellow]配置策略參數: {strategy_name}[/bold yellow]")
        final_params = {}
        for param_id, info in strategy.requirements.items():
            default_val = str(info.get('default', ''))
            
            # 動態調整預設值 (例如根據 investment_mode 決定金額)
            dyn_map = info.get('dynamic_defaults')
            if dyn_map:
                mode = final_params.get('investment_mode')
                if mode in dyn_map:
                    default_val = str(dyn_map[mode])

            desc = f"{info['description']} (預設: {default_val}):"
            choices = info.get('choices')

            if choices:
                val = await questionary.select(desc, choices=choices, default=default_val, style=custom_style).ask_async()
            else:
                val = await questionary.text(desc, default=default_val, style=custom_style).ask_async()
            
            final_params[param_id] = val if val != "" else info.get('default')

        # 確保引擎中只有一個自主策略
        self.engine.active_strategies = []
        self.engine.add_strategy(strategy, final_params)

    async def _setup_signals_flow(self, exchange):
        signal_cfg = self.config.get('signals', {})
        if not signal_cfg or not signal_cfg.get('enabled'):
            console.print("[red]⚠ 警告: YAML 中尚未啟用訊號源或配置為停用[/red]")
            return
        
        sources = signal_cfg.get('sources', [])
        if not sources:
            console.print("[red]⚠ 警告: YAML 中沒有定義任何訊號源[/red]")
            return
        
        # 1. 選擇要監聽的頻道
        from questionary import Choice
        choices = [Choice(s['name'], checked=False) for s in sources]
        selected_names = await questionary.checkbox(
            "請選擇要監聽的訊號源 (多選):",
            choices=choices,
            instruction="(使用方向鍵移動, <空白鍵> 選擇, <a> 全選, <i> 全反選)",
            validate=lambda x: True if len(x) > 0 else "請至少選擇一項策略運行",
            style=custom_style
        ).ask_async()
        
        if selected_names is None: return # 處理 Ctrl+C 的情況

        selected_sources = [s for s in sources if s['name'] in selected_names]
        self.engine.active_strategies = []

        # 2. 為每個選定的頻道配置獨立策略與參數
        for src in selected_sources:
            chan_name = src['name']
            strat_name = src.get('strategy')
            if not strat_name: continue

            console.print(f"\n[bold blue]>>> 為頻道『{chan_name}』配置參數 ({strat_name})[/bold blue]")
            strategy = StrategyFactory.create_strategy(strat_name, exchange)
            strategy.target_source = chan_name # 綁定來源
            
            final_params = {}
            for param_id, info in strategy.requirements.items():
                default_val = str(info.get('default', ''))
                
                # 動態調整預設值
                dyn_map = info.get('dynamic_defaults')
                if dyn_map:
                    mode = final_params.get('investment_mode')
                    if mode in dyn_map:
                        default_val = str(dyn_map[mode])

                desc = f"{chan_name} - {info['description']} (預設: {default_val}):"
                choices = info.get('choices')

                if choices:
                    val = await questionary.select(desc, choices=choices, default=default_val, style=custom_style).ask_async()
                else:
                    val = await questionary.text(desc, default=default_val, style=custom_style).ask_async()
                
                final_params[param_id] = val if val != "" else info.get('default')
            
            self.engine.add_strategy(strategy, final_params)

        # 3. 註冊連線配置
        self.selected_signal_config = signal_cfg.copy()
        self.selected_signal_config['sources'] = selected_sources
        self.engine.setup_signal_sources(self.selected_signal_config)
        console.print(f"\n[green]✔ 訊號監控初始化完成 (啟動 {len(selected_sources)} 個頻道)[/green]")
