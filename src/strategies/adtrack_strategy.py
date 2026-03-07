import asyncio
import re
import json
import os
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from src.core.strategy_base import StrategyBase

console = Console()

class AdTrack(StrategyBase):
    """
    AdTrack 交易策略 V5.0 (多交易所路由版)。
    新增功能:
    1. 多交易所自動選擇 (依槓桿支援最佳化)。
    2. 槓桿縮減防護 (原倍數-25，floor=25)。
    3. 跨所重複進場防護。
    """

    def __init__(self, exchange, router=None):
        super().__init__(exchange)
        # router 為 ExchangeRouter 實例 (多所路由)，未提供則僅用 self.exchange
        self.router = router
        self.watched_trades = []
        self._monitoring_task = None
        self._persistence_file = "data/active_trades.json"
        self._signal_history_file = "data/signal_history.json"
        self._last_reconciled = 0 # 上次自動對診時間

    def on_init(self, params: Dict[str, Any]) -> None:
        """配置階段：僅載入存檔與參數，不啟動背景工作"""
        super().on_init(params)
        self._load_trades()
        # 這裡不啟動 task，確保選單介面乾淨

    async def start(self) -> None:
        """啟動階段：使用者確認啟動後，才開始監控與掃描"""
        if not self._monitoring_task:
            self.is_running = True
            # 重設時間戳，確保啟動瞬發第一次掃描
            self._last_reconciled = 0 
            self._monitoring_task = asyncio.create_task(self._monitor_loop())
            console.print(f"[bold cyan][{self.strategy_name}] 背景監控與自動對接任務已啟動[/bold cyan]")

    # --- 槓桿縮減公式 (AdTrack 專屬) ---
    @staticmethod
    def _apply_leverage_reduction(original_leverage: int) -> int:
        """原倍數 > 25 時減去25；已是 25X 以下則不調整"""
        if original_leverage <= 25:
            return original_leverage
        return max(original_leverage - 25, 1)

    def on_signal(self, signal_data: Dict[str, Any], source: str) -> None:
        # --- 來源過濾邏輯：確保此實例只處理其綁定頻道的訊號 ---
        if hasattr(self, 'target_source') and self.target_source and source != self.target_source:
            return

        # --- 訊號日誌 ---
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
        # --- 步驟 0：紀錄訊號歷史 (用於自動對接) ---
        self._record_signal(signal_data)

        symbol = signal_data.get("symbol")
        side = signal_data.get("side")
        raw_leverage = int(signal_data.get("leverage", 1))
        # ... 後續邏輯

        # --- 步驟 A：槓桿縮減 (AdTrack 專屬規則) ---
        leverage = self._apply_leverage_reduction(raw_leverage)
        if leverage != raw_leverage:
            console.print(f"[yellow][AdTrack] 槓桿縮減：{raw_leverage}X → {leverage}X (原倍數-25)[/yellow]")

        # --- 步驟 B：跨所查詢重複持倉保護 ---
        if self.router:
            open_symbols = self.router.get_all_open_symbols()
        else:
            try:
                positions = self.exchange.get_open_positions()
                open_symbols = {p.get('symbol', '') for p in positions}
            except Exception:
                open_symbols = set()

        if symbol in open_symbols:
            console.print(f"[yellow][AdTrack] 跳過：{symbol} 已存在持倉，不重複進場[/yellow]")
            return

        # --- 步驟 C：選出最佳交易所 ---
        if self.router:
            target_exchange = self.router.select_best_exchange(symbol, leverage)
            if not target_exchange:
                console.print(f"[red][AdTrack] 所有交易所均不支援 {symbol}，放棄本次訊號[/red]")
                return
        else:
            target_exchange = self.exchange

        try:
            # 1. 設置交易所環境
            try: target_exchange._exchange.set_margin_mode('cross', symbol)
            except: pass
            try: target_exchange._exchange.set_position_mode(False, symbol)
            except: pass

            try:
                target_exchange.set_leverage(leverage, symbol)
            except Exception as lev_e:
                err_msg = str(lev_e)
                if "gt maxLeverage" in err_msg:
                    match = re.search(r"maxLeverage \[(\d+)\]", err_msg)
                    if match:
                        max_lev_val = int(match.group(1))
                        suggested_lev = int(max_lev_val / 100)
                        console.print(f"[yellow][AdTrack] 槓桿超限：自動調降為 {suggested_lev}X...[/yellow]")
                        try: target_exchange.set_leverage(suggested_lev, symbol)
                        except: console.print("[red][AdTrack] 槓桿自動修正失敗[/red]")
                elif "110043" in err_msg.lower() or "leverage not modified" in err_msg.lower():
                    pass  # 已是目標槓桿，靜默忽略
                else:
                    console.print(f"[yellow][AdTrack Leverage Warning] {lev_e}[/yellow]")

            # 2. 測量行情與計算數量 (關鍵：傳入 target_exchange 以取得正確的精度處理)
            ticker = target_exchange.get_ticker(symbol)
            current_price = ticker['last']
            mode = self.params.get("investment_mode", "USDT")
            val = self.params.get("investment_value", 5.0)
            
            amount = self.calculate_order_amount(
                symbol, current_price, val, mode=mode, leverage=leverage, ex=target_exchange
            )
            console.print(f"[dim][AdTrack] 下單模式: {mode} | 保證金: {val} USDT | 槓桿: {leverage}X | 合約數量: {amount}[/dim]")

            # 3. 判定進場方式 (混合進場邏輯：區間內市價，區間外限價)
            is_in_range = entry_min <= current_price <= entry_max
            
            if is_in_range:
                order_type = 'market'
                exec_price = None
                console.print(f"[bold yellow][AdTrack] 現價 {current_price} 位於區間內 ({entry_min} - {entry_max})，執行市價進場！[/bold yellow]")
            else:
                order_type = 'limit'
                # 買入時若現價過高則掛區間上限；賣出時若現價過低則掛區間下限
                if side == 'buy':
                    exec_price = entry_max if current_price > entry_max else current_price
                else:
                    exec_price = entry_min if current_price < entry_min else current_price
                console.print(f"[bold blue][AdTrack] 現價 {current_price} 暫不在區間內，改為限價掛單 @ {exec_price}[/bold blue]")

            # 4. 執行下單 (透過 target_exchange)
            # 對於限價單，我們也嘗試在參數中帶入第一階 TP 與 總 SL (針對 Bybit V5 介面連動)
            extra_params = {'positionIdx': 0}
            if order_type == 'limit' and tp_prices:
                extra_params.update({
                    'takeProfit': str(tp_prices[0]), 
                    'stopLoss': str(sl_price),
                    'tpslMode': 'Partial'
                })

            main_order = target_exchange.create_order(symbol, order_type, side, amount, exec_price, extra_params)

            if main_order:
                if order_type == 'market':
                    from datetime import datetime
                    now_str = datetime.now().strftime("%H:%M:%S")

                    tp_orders_info, sl_id = await self._set_multi_tp_sl(
                        symbol, side, amount, sl_price, tp_prices, target_exchange
                    )
                    self.watched_trades.append({
                        "symbol": symbol, "side": side, "entry_price": current_price,
                        "tp_orders": tp_orders_info, "sl_order_id": sl_id,
                        "tp_history": tp_prices, "current_tp_stage": 0,
                        "remaining_amount": amount, "timestamp": now_str,
                        "exchange": target_exchange  # 記住是哪個所的單
                    })
                    self._save_trades() # 持久化存檔
                    console.print(f"[bold green]✔ {symbol} 市價進場成功！| 所: {target_exchange.exchange_id} | TP/SL 設置完畢[/bold green]")
                else:
                    console.print(f"[bold green]✔ {symbol} 限價掛單成功！價格: {exec_price} | 已預設首階 TP 及 SL[/bold green]")

        except Exception as e:
            # 詳盡日誌：顯示具體出錯位置
            import traceback
            err_trace = traceback.format_exc()
            console.print(f"[red][AdTrack Execution Error] 出錯位置:\n{err_trace}[/red]")

    async def _monitor_loop(self):
        import time
        while self.is_running:
            try:
                now = time.time()
                # A. 每 5 分鐘執行一次方案 B：自動對診
                if now - self._last_reconciled >= 300:
                    await self._auto_reconcile_positions()
                    self._last_reconciled = now

                # B. 每 5 秒檢查一次持倉成交狀態
                if hasattr(self, 'engine'):
                    self.engine.stats['active_trades'] = self.watched_trades

                for trade in self.watched_trades[:]:
                    await self._check_trade_update(trade)
                
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                # console.print(f"[AdTrack Monitor Error] {e}") 
                await asyncio.sleep(10)

    async def _check_trade_update(self, trade):
        """檢查單筆交易的成交狀況 (增加生存校驗)"""
        symbol = trade['symbol']
        side = trade['side']
        tp_orders = trade['tp_orders']
        ex = trade.get('exchange', self.exchange)

        # --- 步驟 A：生存校驗 (確認持倉是否還在) ---
        try:
            # 獲取該交易所所有持倉
            positions = ex.get_open_positions()
            # 找到對應幣種的持倉量
            pos = next((p for p in positions if p['symbol'] == symbol), None)
            size = abs(float(pos.get('contracts', 0) or pos.get('size', 0))) if pos else 0
            
            if size == 0:
                console.print(f"[dim yellow][AdTrack] {symbol} 場上持倉已歸零 (可能已手動平倉或止損)，停止監控。[/dim yellow]")
                if trade in self.watched_trades:
                    self.watched_trades.remove(trade)
                    self._save_trades()
                return
            
            # 同步目前的剩餘持倉量 (用於後續移動止損)
            trade['remaining_amount'] = size
        except Exception as e:
            # 網路暫時出錯則跳過，不輕易刪除監控
            # console.print(f"[dim red]生存校驗失敗 ({symbol}): {e}[/dim red]")
            pass

        # --- 步驟 B：原有監控與混合型止損邏輯 ---
        for tp in tp_orders[:]:
            try:
                status = None
                try:
                    order_info = ex.get_order(tp['id'], symbol)
                    status = order_info.get('status')
                except Exception as e:
                    # 如果是因為 500 筆限制或找不到，啟動「混合型止損」價格判定
                    if "last 500 orders" in str(e).lower() or "not found" in str(e).lower():
                        ticker = ex.get_ticker(symbol)
                        current_price = ticker['last']
                        target_price = tp['price']
                        
                        # 判定是否「價格過位」
                        is_hit = (side == 'buy' and current_price >= target_price) or \
                                 (side == 'sell' and current_price <= target_price)
                        
                        if is_hit:
                            status = 'closed' # 標記為成交，強制推進
                            console.print(f"[bold yellow][混合型止損] ID {tp['id']} 已由價格過位判定為成交 (現價:{current_price} >= 目標:{target_price})[/bold yellow]")
                    else:
                        raise e

                if status == 'closed' or status == 'filled':
                    stage = tp['stage']
                    if stage > trade['current_tp_stage']:
                        console.print(f"[bold green]✔ TP{stage} 已確認達成！執行移動止損...[/bold green]")
                        trade['current_tp_stage'] = stage
                        await self._move_stop_loss(trade, stage)
                        tp_orders.remove(tp)
                        self._save_trades()
                elif status in ['canceled', 'expired']:
                    console.print(f"[yellow][AdTrack] 警告: TP{tp['stage']} 訂單狀態異常 ({status})[/yellow]")
                    tp_orders.remove(tp)
                    self._save_trades()
            except Exception as e:
                console.print(f"[dim red][AdTrack] 監控 ID {tp['id']} 失敗: {e}[/dim red]")

        if not tp_orders:
            self.watched_trades.remove(trade)
            self._save_trades() # 移除交易時存檔

    async def _move_stop_loss(self, trade, stage):
        symbol = trade['symbol']
        side = trade['side']
        close_side = 'sell' if side == 'buy' else 'buy'
        new_sl_price = trade['entry_price'] if stage == 1 else trade['tp_history'][stage - 2]
        ex = trade.get('exchange', self.exchange)  # 使用記錄的交易所

        try:
            if trade.get('sl_order_id'):
                try: ex.cancel_order(trade['sl_order_id'], symbol)
                except: pass

            trigger_direction = "descending" if side == 'buy' else "ascending"
            new_sl_order = ex.create_order(
                symbol, 'market', close_side, trade['remaining_amount'], None,
                {'stopPrice': new_sl_price, 'triggerDirection': trigger_direction,
                 'reduceOnly': True, 'positionIdx': 0}
            )
            trade['sl_order_id'] = new_sl_order['id'] if new_sl_order else None
            if trade['sl_order_id']:
                self._save_trades() # SL ID 更新時存檔
                console.print(f"[green][AdTrack] ✔ 移動止損成功 → {trigger_direction} @ {new_sl_price}[/green]")
        except Exception as e:
            console.print(f"[red][AdTrack SL Error] 移動止損失敗: {e}[/red]")

    async def _set_multi_tp_sl(self, symbol, side, total_amount, initial_sl, tp_list, ex=None):
        """設置多階止盈與初始止損。ex 為目標交易所適配器。"""
        if ex is None:
            ex = self.exchange
        close_side = 'sell' if side == 'buy' else 'buy'

        alloc_str = self.params.get("tp_allocation", "0.25, 0.25, 0.25, 0.25")
        try:
            allocations = [float(x.strip()) for x in alloc_str.split(",")]
        except Exception:
            allocations = [1.0 / len(tp_list)] * len(tp_list)

        tp_infos = []
        for i, tp_p in enumerate(tp_list):
            if i >= len(allocations):
                break
            qty = total_amount * allocations[i]
            qty = float(ex._exchange.amount_to_precision(symbol, qty))
            try:
                order = ex.create_order(symbol, 'limit', close_side, qty, tp_p,
                                        {'reduceOnly': True, 'positionIdx': 0})
                if order:
                    tp_infos.append({"id": order['id'], "price": tp_p, "stage": i + 1})
            except Exception:
                pass

        sl_id = None
        try:
            trigger_direction = "descending" if side == 'buy' else "ascending"
            sl_order = ex.create_order(
                symbol, 'market', close_side, total_amount, None,
                {'stopPrice': initial_sl, 'triggerDirection': trigger_direction,
                 'reduceOnly': True, 'positionIdx': 0}
            )
            sl_id = sl_order['id'] if sl_order else None
            if sl_id:
                console.print(f"[green][AdTrack] ✔ 止損單設置成功: {trigger_direction} @ {initial_sl}[/green]")
            else:
                console.print("[yellow][AdTrack] ⚠️ 止損單回傳為空，請手動確認[/yellow]")
        except Exception as sl_e:
            console.print(f"[red][AdTrack SL Error] 止損設置失敗: {sl_e}[/red]")

        return tp_infos, sl_id

    def on_tick(self, data: Dict[str, Any]) -> None:
        pass

    # --- 持久化邏輯 ---
    # --- 持久化與自動對接機制 (方案 B) ---
    def _record_signal(self, signal: Dict[str, Any]):
        """紀錄訊號到歷史檔案中"""
        try:
            from datetime import datetime
            os.makedirs(os.path.dirname(self._signal_history_file), exist_ok=True)
            
            history = []
            if os.path.exists(self._signal_history_file):
                with open(self._signal_history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            
            signal_entry = dict(signal)
            signal_entry['timestamp_received'] = datetime.now().isoformat()
            history.append(signal_entry)
            
            # 僅保留最近 50 筆
            history = history[-50:]
            with open(self._signal_history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=4, ensure_ascii=False)
        except Exception as e:
            console.print(f"[dim red]訊號歷史紀錄失敗: {e}[/dim red]")

    async def _auto_reconcile_positions(self):
        """自動對接場上未記錄的持倉 (方案 B)"""
        console.print("[dim cyan][AdTrack] 正在掃描全交易所持倉以進行自動對接...[/dim cyan]")
        
        # 獲取所有初始化的交易所
        adapters = self.router._adapters.values() if self.router else [self.exchange]
        
        for ex in adapters:
            try:
                positions = ex.get_open_positions()
                if not positions: continue
                
                # 取得該所所有掛單，用於分析 TP/SL
                all_orders = ex._exchange.fetch_open_orders() 

                for pos in positions:
                    symbol = pos['symbol']
                    # 如果已經在監控中，跳過
                    if any(t['symbol'] == symbol for t in self.watched_trades):
                        continue
                    
                    side = 'buy' if float(pos.get('contracts', 0) or pos.get('size', 0)) > 0 else 'sell'
                    entry_price = float(pos.get('entryPrice', 0))
                    amount = abs(float(pos.get('contracts', 0) or pos.get('size', 0)))
                    
                    if amount == 0: continue

                    console.print(f"[yellow][AdTrack] 發現未知持倉: {symbol} @ {ex.exchange_id}，嘗試自動對接...[/yellow]")
                    
                    # 1. 嘗試從訊號歷史找匹配 (最近 24 小時)
                    matched_signal = None
                    if os.path.exists(self._signal_history_file):
                        with open(self._signal_history_file, 'r', encoding='utf-8') as f:
                            history = json.load(f)
                        for sig in reversed(history):
                            if sig['symbol'] == symbol:
                                matched_signal = sig
                                break
                    
                    # 2. 分析現有掛單以提取 TP/SL
                    tp_orders_info = []
                    sl_id = None
                    tp_history = []
                    
                    # 過濾此幣種的單
                    orders = [o for o in all_orders if o['symbol'] == symbol]
                    for o in orders:
                        # 止損單判定 (通常 Bybit 帶有 stopPrice)
                        if o.get('stopPrice') or o.get('type') == 'stop_market':
                            sl_id = o['id']
                        else:
                            # 判定為 TP 單（假如價格在方向正確的位置）
                            tp_orders_info.append({
                                'id': o['id'], 
                                'price': o['price'], 
                                'stage': len(tp_orders_info) + 1
                            })
                            tp_history.append(o['price'])

                    # 3. 領養它！
                    adopted_trade = {
                        "symbol": symbol,
                        "side": side,
                        "entry_price": entry_price,
                        "tp_orders": tp_orders_info,
                        "sl_order_id": sl_id,
                        "tp_history": tp_history if tp_history else (matched_signal['take_profits'] if matched_signal else []),
                        "current_tp_stage": 0, # 自動對接暫定為 0 階
                        "remaining_amount": amount,
                        "timestamp": "Auto-Adopted",
                        "exchange": ex
                    }
                    
                    self.watched_trades.append(adopted_trade)
                    console.print(f"[bold green]✔ 自動對接成功: {symbol} ({side.upper()}) | 偵測到 {len(tp_orders_info)} 筆止盈單[/bold green]")
                
                self._save_trades()
            except Exception as e:
                console.print(f"[dim red]交易所 {ex.exchange_id} 自動對接失敗: {e}[/dim red]")

    def _save_trades(self):
        """將目前監測中的活躍倉位存入 JSON"""
        try:
            os.makedirs(os.path.dirname(self._persistence_file), exist_ok=True)
            serializable_trades = []
            for t in self.watched_trades:
                dump = dict(t)
                # 交易所物件無法直接轉 JSON，只存其 ID
                ex = t.get('exchange')
                dump['exchange_id'] = ex.exchange_id if ex else None
                if 'exchange' in dump: del dump['exchange']
                serializable_trades.append(dump)
            
            with open(self._persistence_file, "w", encoding="utf-8") as f:
                json.dump(serializable_trades, f, indent=4, ensure_ascii=False)
        except Exception as e:
            console.print(f"[red]AdTrack 持久化儲存失敗: {e}[/red]")

    def _load_trades(self):
        """從 JSON 載入先前的活躍倉位"""
        if not os.path.exists(self._persistence_file):
            return
        
        try:
            with open(self._persistence_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            restored_count = 0
            for dump in data:
                # 恢復交易所物件調度
                ex_id = dump.get('exchange_id')
                target_ex = None
                
                if self.router and ex_id in self.router._adapters:
                    target_ex = self.router._adapters[ex_id]
                elif self.exchange and self.exchange.exchange_id == ex_id:
                    target_ex = self.exchange
                
                if target_ex:
                    dump['exchange'] = target_ex
                    self.watched_trades.append(dump)
                    restored_count += 1
                else:
                    console.print(f"[yellow]AdTrack 無法為 {dump['symbol']} 恢復交易所 {ex_id}，該筆監控已跳過[/yellow]")
            
            if restored_count > 0:
                console.print(f"[bold cyan]AdTrack 已從存檔恢復 {restored_count} 筆持倉監控[/bold cyan]")
        except Exception as e:
            console.print(f"[red]AdTrack 載入存檔失敗: {e}[/red]")

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
                "description": "下單數值 (USDT金額 或 幣種顆數)",
                "default": 5.0,
                "dynamic_defaults": {"UNITS": "0.001", "USDT": "5.0"}
            },
            "tp_allocation": {
                "type": "str",
                "description": "止盈分配比例 (逗號分隔)",
                "default": "0.25, 0.25, 0.25, 0.25"
            }
        }

    @property
    def strategy_name(self) -> str:
        return "AdTrack"
