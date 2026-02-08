import asyncio
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from src.core.strategy_base import StrategyBase

console = Console()

class AdTrack(StrategyBase):
    """
    AdTrack 交易策略 V4.0 (Bybit 特化版)。
    優化: 
    1. 視覺化訊號日誌。
    2. 智慧金額換算 (固定 USDT 成本)。
    3. 自動監控監測與移動止損。
    """

    def __init__(self, exchange):
        super().__init__(exchange)
        self.watched_trades = []
        self._monitoring_task = None

    def on_init(self, params: Dict[str, Any]) -> None:
        super().on_init(params)
        if not self._monitoring_task:
            self._is_running = True
            self._monitoring_task = asyncio.create_task(self._monitor_loop())

    def on_signal(self, signal_data: Dict[str, Any]) -> None:
        # --- 1. 優化日誌輸出 (視覺化訊號內容) ---
        self._log_signal_summary(signal_data)
        
        # 啟動非同步執行流程
        asyncio.create_task(self._process_adtrack_execution(signal_data))

    def _log_signal_summary(self, signal: Dict[str, Any]):
        """使用 Rich 輸出美觀的訊號摘要"""
        table = Table(show_header=False, box=None)
        table.add_row("交易對", f"[bold cyan]{signal['symbol']}[/bold cyan]")
        table.add_row("方向", f"[bold {'green' if signal['side']=='buy' else 'red'}]{signal['side'].upper()}[/bold {'green' if signal['side']=='buy' else 'red'}]")
        table.add_row("槓桿", f"{signal['leverage']}X")
        table.add_row("區間", f"{signal['entry_min']} - {signal['entry_max']}")
        table.add_row("止損", f"[red]{signal['stop_loss']}[/red]")
        table.add_row("止盈", f"[green]{', '.join(map(str, signal['take_profits']))}[/green]")

        console.print(Panel(table, title="[bold yellow]🔔 收到 AdTrack 交易訊號[/bold yellow]", border_style="yellow", expand=False))

    async def _process_adtrack_execution(self, signal_data: Dict[str, Any]):
        symbol = signal_data.get("symbol")
        side = signal_data.get("side")
        leverage = signal_data.get("leverage", 1)
        entry_min = signal_data.get("entry_min")
        entry_max = signal_data.get("entry_max")
        sl_price = signal_data.get("stop_loss")
        tp_prices = signal_data.get("take_profits", [])

        try:
            # 1. 設置 Bybit 環境
            try: self.exchange._exchange.set_margin_mode('cross', symbol)
            except: pass
            try: self.exchange._exchange.set_position_mode(False, symbol)
            except: pass
            self.exchange._exchange.set_leverage(leverage, symbol)

            # 2. 獲取市價並計算數量 (智慧換算)
            ticker = self.exchange.get_ticker(symbol)
            current_price = ticker['last']
            
            # 從參數讀取模式 (預設 USDT) 與 數值
            mode = self.params.get("investment_mode", "USDT")
            val = self.params.get("investment_value", 100.0)
            
            amount = self.calculate_order_amount(symbol, current_price, val, mode=mode)
            
            print(f"[AdTrack] 下單模式: {mode} | 數值: {val} -> 計算量: {amount}")

            # 3. 判定進場方式
            is_in_range = entry_min <= current_price <= entry_max
            order_type = 'market' if is_in_range else 'limit'
            exec_price = None if is_in_range else (entry_min if side == 'sell' else entry_max)

            # 4. 執行下單
            main_order = self.execute_trade(
                symbol=symbol, side=side, amount=amount, 
                order_type=order_type, price=exec_price
            )

            if main_order:
                print(f"[AdTrack] 主單成功: {symbol} @ {exec_price or 'Market'}")
                if order_type == 'market':
                    # 紀錄進場時間
                    from datetime import datetime
                    now_str = datetime.now().strftime("%H:%M:%S")
                    
                    tp_orders_info, sl_id = await self._set_multi_tp_sl(symbol, side, amount, sl_price, tp_prices)
                    self.watched_trades.append({
                        "symbol": symbol, "side": side, "entry_price": current_price,
                        "tp_orders": tp_orders_info, "sl_order_id": sl_id,
                        "tp_history": tp_prices, "current_tp_stage": 0, "remaining_amount": amount,
                        "timestamp": now_str
                    })

        except Exception as e:
            print(f"[AdTrack Error] {e}")

    async def _monitor_loop(self):
        while self._is_running:
            try:
                # 同步持倉狀態至 UI 統計
                if hasattr(self, 'engine'):
                    self.engine.stats['active_trades'] = self.watched_trades

                for trade in self.watched_trades[:]:
                    await self._check_trade_update(trade)
                await asyncio.sleep(5)
            except: await asyncio.sleep(10)

    async def _check_trade_update(self, trade):
        """檢查單筆交易的成交狀況 (強化版: 顯式狀態對比)"""
        symbol = trade['symbol']
        tp_orders = trade['tp_orders']
        
        for tp in tp_orders[:]:
            try:
                # 顯式獲取訂單狀態
                order_info = self.exchange.get_order(tp['id'], symbol)
                status = order_info.get('status') # 'open', 'closed', 'canceled'
                
                if status == 'closed':
                    stage = tp['stage']
                    if stage > trade['current_tp_stage']:
                        console.print(f"[bold green]✔ TP{stage} 已確認成交 (@{tp['price']})！執行移動止損...[/bold green]")
                        trade['current_tp_stage'] = stage
                        await self._move_stop_loss(trade, stage)
                        tp_orders.remove(tp)
                elif status == 'canceled':
                    print(f"[AdTrack] 警告: TP{tp['stage']} 訂單被取消，停止追蹤該止盈點。")
                    tp_orders.remove(tp)
            except Exception as e:
                # 某些交易所可能在訂單完成太快時查不到 (或是 ID 錯誤)
                # 這裡保持靜默或簡易 Log
                pass
        
        if not tp_orders: self.watched_trades.remove(trade)

    async def _move_stop_loss(self, trade, stage):
        symbol = trade['symbol']
        side = trade['side']
        close_side = 'sell' if side == 'buy' else 'buy'
        new_sl_price = trade['entry_price'] if stage == 1 else trade['tp_history'][stage-2]
        
        try:
            if trade.get('sl_order_id'):
                try: self.exchange.cancel_order(trade['sl_order_id'], symbol)
                except: pass

            new_sl_order = self.execute_trade(
                symbol=symbol, order_type='market', side=close_side,
                amount=trade['remaining_amount'], 
                params={'stopPrice': new_sl_price, 'reduceOnly': True}
            )
            trade['sl_order_id'] = new_sl_order['id'] if new_sl_order else None
        except Exception as e:
            print(f"[AdTrack SL Error] {e}")

    async def _set_multi_tp_sl(self, symbol, side, total_amount, initial_sl, tp_list):
        close_side = 'sell' if side == 'buy' else 'buy'
        partial_amount = self.calculate_order_amount(symbol, 1.0, total_amount / 4, mode='UNITS')
        
        tp_infos = []
        for i, tp_p in enumerate(tp_list[:4]):
            try:
                order = self.execute_trade(
                    symbol=symbol, order_type='limit', side=close_side,
                    amount=partial_amount, price=tp_p, params={'reduceOnly': True}
                )
                if order: tp_infos.append({"id": order['id'], "price": tp_p, "stage": i+1})
            except: pass

        sl_id = None
        try:
            sl_order = self.execute_trade(
                symbol=symbol, order_type='market', side=close_side,
                amount=total_amount, params={'stopPrice': initial_sl, 'reduceOnly': True}
            )
            sl_id = sl_order['id'] if sl_order else None
        except: pass
        
        return tp_infos, sl_id

    def on_tick(self, data: Dict[str, Any]) -> None: pass

    @property
    def requirements(self) -> Dict[str, Any]: 
        return {
            "investment_mode": {"type": "string", "description": "下單模式 (USDT 或 UNITS)", "default": "USDT"},
            "investment_value": {"type": "float", "description": "下單數值 (USDT金額 或 幣種顆數)", "default": 100.0}
        }

    @property
    def strategy_name(self) -> str: return "AdTrack"
