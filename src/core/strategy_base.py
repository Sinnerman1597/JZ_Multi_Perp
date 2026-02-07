from abc import ABC
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

    def execute_trade(self, symbol: str, side: str, amount: float, price: Optional[float] = None):
        """
        封裝下單邏輯，加入基本的風險檢查。
        side: 'buy' or 'sell'
        """
        # 這裡可以加入全局風險檢查 (例如單筆金額上限)
        print(f"[Trade Executing] {self.strategy_name} -> {side} {amount} {symbol} @ {price or 'Market'}")
        
        try:
            order_type = 'limit' if price else 'market'
            return self.exchange.create_order(
                symbol=symbol,
                order_type=order_type,
                side=side,
                amount=amount,
                price=price
            )
        except Exception as e:
            print(f"[Trade Error] 執行下單失敗: {e}")
            return None

    @property
    def strategy_name(self) -> str:
        return self.__class__.__name__
