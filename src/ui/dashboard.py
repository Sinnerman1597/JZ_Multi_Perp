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
            Layout(name="upper", size=9),  # 統計數據
            Layout(name="middle", size=9), # 持倉狀態
            Layout(name="lower", size=10), # 訊息日誌 (擴大以佔滿底部)
        )
        return layout

    @staticmethod
    def get_header_panel():
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return Panel(f"[bold green]JZ_Multi_Perp 交易監控中心[/bold green] | 系統時間: {now}", style="blue")

    @staticmethod
    def get_stats_panel(stats, exchange_id):
        table = Table(show_header=False, box=None)
        table.add_row("當前交易所:", f"[yellow]{exchange_id.upper()}[/yellow]")
        table.add_row("系統狀態:", f"[bold {'green' if '監聽中' in stats.get('status', '') else 'yellow'}]{stats.get('status', '初始化...')}[/bold {'green' if '監聽中' in stats.get('status', '') else 'yellow'}]")
        table.add_row("監聽頻道:", f"[magenta]{stats.get('active_channels', 'None')}[/magenta]")
        table.add_row("已接收訊號:", str(stats['total_signals']))
        table.add_row("已執行下單:", str(stats['executed_trades']))
        table.add_row("最後訊號時間:", str(stats['last_signal_time']))
        return Panel(table, title="[bold white]核心統計[/bold white]", border_style="cyan")

    @staticmethod
    def get_trades_panel(active_trades):
        table = Table(expand=True)
        table.add_column("時間", style="dim")
        table.add_column("交易對", style="yellow")
        table.add_column("方向", style="bold")
        table.add_column("進場價", style="white")
        table.add_column("當前狀態", style="green")
        table.add_column("剩餘量", style="magenta")

        if not active_trades:
            return Panel("[dim]目前無活動持倉[/dim]", title="[bold white]活動持倉監控[/bold white]", border_style="green")

        for t in active_trades:
            side_style = "red" if t['side'] == 'sell' else "blue"
            table.add_row(
                t.get('timestamp', 'N/A'),
                t['symbol'], 
                f"[{side_style}]{t['side'].upper()}[/{side_style}]",
                str(t['entry_price']),
                f"TP級別: {t['current_tp_stage']}",
                str(t['remaining_amount'])
            )
        return Panel(table, title="[bold white]活動持倉監控[/bold white]", border_style="green")

    @staticmethod
    def get_logs_panel(logs):
        content = "\n".join(logs) if logs else "[dim]尚無訊息紀錄...[/dim]"
        return Panel(content, title="[bold white]最近訊號日誌 (前5筆)[/bold white]", border_style="yellow")
