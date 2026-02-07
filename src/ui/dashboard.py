from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.console import Console
from datetime import datetime

class Dashboard:
    @staticmethod
    def create_layout() -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", size=10),
            Layout(name="footer", size=3),
        )
        return layout

    @staticmethod
    def get_header_panel():
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return Panel(f"[bold green]Multi_Base 交易監控中心[/bold green] | 系統時間: {now}", style="blue")

    @staticmethod
    def get_stats_panel(stats, exchange_id):
        table = Table(show_header=False, box=None)
        table.add_row("當前交易所:", f"[yellow]{exchange_id.upper()}[/yellow]")
        table.add_row("已接收訊號:", str(stats['total_signals']))
        table.add_row("已執行下單:", str(stats['executed_trades']))
        table.add_row("最後訊號時間:", str(stats['last_signal_time']))
        return Panel(table, title="[bold white]實時數據[/bold white]", border_style="cyan")

    @staticmethod
    def get_footer_panel():
        return Panel("可用指令: [bold yellow]stop[/bold yellow] (停止引擎並退出) | 測試訊號: [bold yellow]test[/bold yellow]", style="dim")
