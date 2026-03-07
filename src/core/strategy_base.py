from abc import ABC, abstractmethod
import asyncio
from typing import Dict, Any, Optional
from src.core.interfaces.strategy_abc import StrategyInterface
from src.core.interfaces.exchange_abc import ExchangeInterface

class StrategyBase(StrategyInterface, ABC):
    """
    策略基類。
    提供通用的工具方法，如風險檢查、日誌封裝與下單代理。
    """
    
    def __init__(self, exchange: ExchangeInterface):
        self.exchange = exchange
        self.params: Dict[str, Any] = {}
        self.is_running = False

    def on_init(self, params: Dict[str, Any]) -> None:
        """預設的初始化邏輯，將傳入參數存入 self.params"""
        self.params = params
        self.is_running = True
        print(f"[Strategy: {self.strategy_name}] 初始化完成")

    async def stop(self) -> None:
        """優化關閉邏輯：停止策略運行並清理背景任務"""
        self.is_running = False
        # 如果子類有背景監控任務，嘗試取消它
        if hasattr(self, '_monitoring_task') and self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        print(f"[Strategy: {self.strategy_name}] 已停止")

    def execute_trade(self, symbol: str, side: str, amount: float, order_type: str = 'limit', price: float = None, params: Dict[str, Any] = {}) -> Dict[str, Any]:
        """執行下單 (封裝底層交易所介面)"""
        try:
            return self.exchange.create_order(symbol, order_type, side, amount, price, params)
        except Exception as e:
            print(f"[Trade Error] {symbol} {side} 下單失敗: {e}")
            return None

    def calculate_order_amount(self, symbol: str, ticker_price: float, val: float, mode: str = 'USDT', leverage: int = 1, ex=None) -> float:
        """
        智慧數量計算器。
        :param val: 數值
            - USDT 模式：代表每筆進場的【保證金（Margin）】，實際倉位大小 = val × leverage
            - UNITS 模式：代表直接下單的數量（顆數）
        :param mode: 'USDT' 或 'UNITS'
        :param leverage: 槓桿倍數，僅 USDT 模式使用
        :param ex: 目標交易所實例，若不提供則使用 default (self.exchange)
        """
        target_ex = ex if ex else self.exchange
        if mode == 'USDT':
            # 保證金 × 槓桿 / 市價 = 數量 (強制型別轉換避免 str/float 錯誤)
            raw_amount = float(val) * int(leverage) / float(ticker_price)
        else:
            raw_amount = float(val)

        # 使用交易所精度處理
        return float(target_ex.amount_to_precision(symbol, raw_amount))

    @property
    def strategy_name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def on_tick(self, data: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def on_signal(self, signal_data: Dict[str, Any]) -> None:
        pass

    @property
    @abstractmethod
    def requirements(self) -> Dict[str, Any]:
        pass
