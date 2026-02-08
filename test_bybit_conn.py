import asyncio
from rich.console import Console
from rich.table import Table
from src.infrastructure.config_loader import ConfigLoader
from src.core.exchange_manager import ExchangeManager

console = Console()

async def test_bybit_connectivity():
    console.print("[bold blue]=== Bybit API 下單連通性測試 ===[/bold blue]\n")

    # 1. 載入配置
    config = ConfigLoader.load_config()
    exchange_cfg = config.get('exchange', {})
    
    # 強制指定 Bybit 進行測試
    exchange_cfg['active'] = 'bybit'
    
    try:
        # 2. 初始化交易所實例
        console.print("[yellow]正在初始化 Bybit 實例...[/yellow]")
        exchange = ExchangeManager.create_exchange(exchange_cfg)
        await asyncio.sleep(10)
        
        # 3. 測試獲取餘額 (驗證 API Key/Secret)
        console.print("[yellow]正在驗證 API 帳戶餘額...[/yellow]")
        balance = exchange.get_balance()
        
        # 顯示餘額摘要
        table = Table(title="帳戶餘額摘要")
        table.add_column("資產", style="cyan")
        table.add_column("可用餘額", style="green")
        
        # 獲取常用美金資產 (USDT/USDC)
        for asset in ['USDT', 'USDC']:
            if asset in balance:
                table.add_row(asset, str(balance[asset]['free']))
        
        console.print(table)
        console.print("[green]✔ API 驗證成功！已成功取得餘額。[/green]\n")
        await asyncio.sleep(10)

        # 4. 測試基本行情獲取
        symbol = "BTC/USDT:USDT"  # Bybit 線性合約格式
        console.print(f"[yellow]正在獲取 {symbol} 即時行情...[/yellow]")
        ticker = exchange.get_ticker(symbol)
        last_price = ticker['last']
        console.print(f"[green]✔ 行情獲取成功！當前價格: {last_price}[/green]\n")
        await asyncio.sleep(10)

        # 5. 模擬下單預檢 (不實際成交，僅驗證下單函數調用)
        console.print("[bold magenta]這是一個連通性腳本，為了安全，預設不執行實際下單。[/bold magenta]")
        console.print("如果您需要測試『實際下單並立刻撤單』，請手動取消下方代碼的註釋。\n")
        
        
        # 取消註釋以測試實際下單 (市價買入 0.001 BTC，然後立即平倉)
        # 注意：這會在您的帳戶產生實試交易費用
        symbol = "BTC/USDT:USDT"
        amount = 0.001 # Bybit BTC 最小下單量
        
        # 5. 測試槓桿與模式設置
        target_leverage = 5
        try:
            console.print(f"[yellow]正在嘗試設置槓桿為 {target_leverage}x...[/yellow]")
            exchange._exchange.set_leverage(target_leverage, symbol)
            console.print("[green]✔ 槓桿設置成功。[/green]")
            await asyncio.sleep(10)
        except Exception as e:
            err_msg = str(e).lower()
            if "110043" in err_msg or "leverage not modified" in err_msg:
                console.print(f"[cyan]提示：槓桿數已為 {target_leverage} 倍，不進行調整。[/cyan]")
            else:
                console.print(f"[red]⚠ 槓桿設置警告: {e}[/red]")

        # 5.1 設置持倉模式 (切換為單向持倉)
        try:
            console.print(f"[yellow]正在嘗試將持倉模式切換為『單向持倉 (One-way)』...[/yellow]")
            # False 代表單向, True 代表雙向
            exchange._exchange.set_position_mode(False, symbol)
            console.print("[green]✔ 持倉模式切換成功。[/green]")
            await asyncio.sleep(10)
        except Exception as mode_e:
            console.print(f"[dim]提示：持倉模式切換跳過 (可能已是該模式或已有持倉): {mode_e}[/dim]")

        # 5.2 驗證保證金模式
        try:
            console.print(f"[yellow]正在驗證保證金模式 (交叉全倉)...[/yellow]")
            exchange._exchange.set_margin_mode('cross', symbol)
            console.print("[green]✔ 全倉模式驗證/切換成功。[/green]")
            await asyncio.sleep(10)
        except Exception as margin_e:
            console.print(f"[dim]提示：模式切換跳過 (可能已是該模式): {margin_e}[/dim]")

        # 6. 執行下單
        console.print(f"[red]🚀 實際下單測試開始：正在市價買入 {amount} {symbol}...[/red]")
        try:
            # 加入 positionIdx: 0 確保單向持倉下單明確
            order = exchange._exchange.create_order(symbol, 'market', 'buy', amount, params={'positionIdx': 0})
            console.print(f"[green]✔ 下單成功！訂單 ID: {order['id']}[/green]")
            
            console.print("[yellow]⏳ 已開倉，等待 20 秒供您確認 (請查看交易所網頁)...[/yellow]")
            await asyncio.sleep(20)
            
            console.print(f"[red]收尾測試：正在嘗試市價全平 (ReduceOnly)...[/red]")
            close_order = exchange._exchange.create_order(symbol, 'market', 'sell', amount, params={'reduceOnly': True, 'positionIdx': 0})
            console.print(f"[green]✔ 平倉完成！測試圓滿結束。[/green]")
        except Exception as order_e:
            err_msg = str(order_e)
            if "10001" in err_msg:
                 console.print(f"[bold red]❌ 下單依舊失敗 (10001)。[/bold red]")
                 console.print("[yellow]這通常意味著 API 無法自動切換持倉模式（因為您帳戶目前有其他幣種的持倉或掛單）。[/yellow]")
                 console.print("[white]請手動到 Bybit 網頁：帳戶設置 -> 持倉模式 -> 切換為『單向持倉模式』。[/white]")
            else:
                raise order_e

    except Exception as e:
        console.print(f"[bold red]❌ 測試失敗！原因: {e}[/bold red]")
        if "AuthenticationError" in str(e):
            console.print("[red]提示：請檢查 config.yaml 中的 apiKey 與 secret 是否正確。[/red]")
        elif "NetworkError" in str(e):
            console.print("[red]提示：網路連線逾時，請檢查是否需要開啟代理(VPN)。[/red]")

if __name__ == "__main__":
    asyncio.run(test_bybit_connectivity())
