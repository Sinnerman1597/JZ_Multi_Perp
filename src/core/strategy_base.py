from abc import ABC, abstractmethod
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

    def execute_trade(self, symbol: str, side: str, amount: float, order_type: str = 'limit', price: float = None, params: Dict[str, Any] = {}) -> Dict[str, Any]:
        """執行下單 (封裝底層交易所介面)"""
        try:
            return self.exchange.create_order(symbol, order_type, side, amount, price, params)
        except Exception as e:
            print(f"[Trade Error] {symbol} {side} 下單失敗: {e}")
            return None

    def calculate_order_amount(self, symbol: str, ticker_price: float, val: float, mode: str = 'USDT') -> float:
        """
        智慧數量計算器。
        :param val: 數值 (如果是 USDT 模式則為金額，如果是 UNITS 模式則為顆數)
        :param mode: 'USDT' 或 'UNITS'
        """
        if mode == 'USDT':
            # 金額 / 市價 = 顆數
            raw_amount = val / ticker_price
        else:
            raw_amount = val

        # 使用交易所精度處理
        return float(self.exchange._exchange.amount_to_precision(symbol, raw_amount))

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
