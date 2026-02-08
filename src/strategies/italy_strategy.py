import asyncio
from typing import Dict, Any, List
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from src.core.strategy_base import StrategyBase

console = Console()

class ItalyStrategy(StrategyBase):
    """
    Italy 交易策略 (英文訊號模式)。
    特點：
    1. 立即市價進場 (不等待區間)。
    2. 自動設置兩階止盈 (各 50% 或依照配置)。
    3. 移動止損保護。
    """

    def __init__(self, exchange):
        super().__init__(exchange)
        self.watched_trades = []
        self._is_running = False
        self._monitoring_task = None

    def on_init(self, params: Dict[str, Any]) -> None:
        super().on_init(params)
        if not self._monitoring_task:
            self._is_running = True
            self._monitoring_task = asyncio.create_task(self._monitor_loop())

    def on_signal(self, signal_data: Dict[str, Any], source: str) -> None:
        # --- 來源過濾邏輯：確保此實例只處理其綁定頻道的訊號 ---
        if hasattr(self, 'target_source') and self.target_source and source != self.target_source:
            return
            
        # 只處理來自 Italy_Channel 的訊號 (或是相關解析器的訊號)
        # 如果是混合模式，這可以確保不會誤吃中文訊號
        table = Table(show_header=False, box=None)
        table.add_row("交易對", f"[bold cyan]{signal_data['symbol']}[/bold cyan]")
        table.add_row("方向", f"[bold {'green' if signal_data['side']=='buy' else 'red'}]{signal_data['side'].upper()}[/bold {'green' if signal_data['side']=='buy' else 'red'}]")
        table.add_row("來源", f"[dim]{source}[/dim]")
        
        console.print(Panel(table, title="[bold magenta]🇮🇹 Italy 訊號觸發 - 市價執行[/bold magenta]", border_style="magenta", expand=False))
        
        asyncio.create_task(self._process_execution(signal_data))

    async def _process_execution(self, signal):
        symbol = signal['symbol']
        side = signal['side']
        leverage = signal['leverage']
        target_tps = signal['take_profits']
        sl_price = signal['stop_loss']

        try:
            # 1. 環境設置 (全倉、單向持倉、槓桿)
            try:
                # True 代表全倉, False 代表逐倉
                self.exchange._exchange.set_margin_mode('cross', symbol)
            except: pass

            try:
                # False 代表單向, True 代表雙向
                self.exchange._exchange.set_position_mode(False, symbol)
            except: pass

            try:
                self.exchange._exchange.set_leverage(leverage, symbol)
            except Exception as lev_e:
                err_msg = str(lev_e).lower()
                if "110043" in err_msg or "leverage not modified" in err_msg:
                    print(f"[Italy Strategy] 提示：{symbol} 槓桿數已為 {leverage} 倍，不進行調整。")
                else:
                    print(f"[Italy Strategy Leverage Warning] {lev_e}")
            
            # 2. 計算數量
            ticker = self.exchange.get_ticker(symbol)
            current_price = ticker['last']
            
            mode = self.params.get("investment_mode", "USDT")
            val = self.params.get("investment_value", 100.0)
            amount = self.calculate_order_amount(symbol, current_price, val, mode=mode)

            # 3. 直下市價單 (Italy 策略核心)
            main_order = self.execute_trade(
                symbol=symbol, side=side, amount=amount, order_type='market',
                params={'positionIdx': 0} # 強制單向持倉
            )

            if main_order:
                # 4. 設置 TP/SL (假設平均分配給 TP1, TP2)
                # 這裡可以根據需要調整 TP 的數量分配
                # 如果只有 2 個 TP，則各 50%
                from datetime import datetime
                now_str = datetime.now().strftime("%H:%M:%S")
                
                tp_info, sl_id = await self._set_tp_sl(symbol, side, amount, sl_price, target_tps)
                
                self.watched_trades.append({
                    "symbol": symbol, "side": side, "entry_price": current_price,
                    "tp_orders": tp_info, "sl_order_id": sl_id,
                    "tp_history": target_tps, "current_tp_stage": 0,
                    "remaining_amount": amount, "timestamp": now_str
                })

        except Exception as e:
            err_msg = str(e)
            if "10001" in err_msg:
                print(f"[Italy Strategy Error] ❌ 下單失敗 (10001): 倉位模式不匹配。")
                print(">>> 解決方案：請手動將 Bybit 該幣種的持倉模式改為『單向持倉 (One-way)』。")
            else:
                print(f"[Italy Strategy Error] {e}")

    async def _set_tp_sl(self, symbol, side, total_amount, sl_price, tps):
        close_side = 'sell' if side == 'buy' else 'buy'
        tp_infos = []
        
        if not tps: return [], None

        # 比例分配：如果有 2 個 TP，各 50%
        qty_per_tp = total_amount / len(tps)
        
        for i, price in enumerate(tps):
            try:
                order = self.execute_trade(
                    symbol=symbol, side=close_side, amount=qty_per_tp,
                    order_type='limit', price=price, params={'reduceOnly': True, 'positionIdx': 0}
                )
                if order:
                    tp_infos.append({"id": order['id'], "price": price, "stage": i+1})
            except: pass

        sl_id = None
        if sl_price:
            try:
                sl_order = self.execute_trade(
                    symbol=symbol, side=close_side, amount=total_amount,
                    order_type='market', params={'stopPrice': sl_price, 'reduceOnly': True, 'positionIdx': 0}
                )
                sl_id = sl_order['id'] if sl_order else None
            except: pass
            
        return tp_infos, sl_id

    async def _monitor_loop(self):
        while self._is_running:
            if hasattr(self, 'engine'):
                self.engine.stats['active_trades'] = self.watched_trades
            
            for trade in self.watched_trades[:]:
                await self._check_update(trade)
            await asyncio.sleep(5)

    async def _check_update(self, trade):
        symbol = trade['symbol']
        for tp in trade['tp_orders'][:]:
            try:
                info = self.exchange.get_order(tp['id'], symbol)
                if info.get('status') == 'closed':
                    trade['current_tp_stage'] = tp['stage']
                    trade['remaining_amount'] -= (trade['remaining_amount'] / (len(trade['tp_orders']))) # 簡易估計
                    # 移動止損 (Italy 邏輯：TP1 達成後 SL 移至開倉價)
                    if tp['stage'] == 1:
                        await self._move_sl(trade, trade['entry_price'])
                    trade['tp_orders'].remove(tp)
            except Exception: pass
        
        if not trade['tp_orders']:
            self.watched_trades.remove(trade)

    async def _move_sl(self, trade, new_price):
        symbol = trade['symbol']
        side = trade['side']
        close_side = 'sell' if side == 'buy' else 'buy'
        if trade.get('sl_order_id'):
            try: self.exchange.cancel_order(trade['sl_order_id'], symbol)
            except: pass
        
        new_sl = self.execute_trade(
            symbol=symbol, side=close_side, amount=trade['remaining_amount'],
            order_type='market', params={'stopPrice': new_price, 'reduceOnly': True, 'positionIdx': 0}
        )
        trade['sl_order_id'] = new_sl['id'] if new_sl else None

    def on_tick(self, data: Dict[str, Any]) -> None: pass

    @property
    def requirements(self) -> Dict[str, Any]:
        return {
            "investment_mode": {
                "type": "list", 
                "description": "下單模式", 
                "default": "USDT",
                "choices": ["USDT", "UNITS"]
            },
            "investment_value": {
                "type": "float", 
                "description": "下單金額", 
                "default": 10.0,
                "dynamic_defaults": {"UNITS": "0.001", "USDT": "10.0"}
            }
        }

    @property
    def strategy_name(self) -> str: return "ItalyStrategy"
