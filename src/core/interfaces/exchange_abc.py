from abc import ABC, abstractmethod
from typing import Dict, Any, List

class ExchangeInterface(ABC):
    """
    交易所抽象基類 (Interface)。
    所有交易所適配器 (Adapters) 必須繼承並實作此類別。
    """

    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        """初始化交易所連接 (API Key, Secret 等)"""
        pass

    @abstractmethod
    def get_balance(self) -> Dict[str, Any]:
        """獲取當前帳戶餘額"""
        pass

    @abstractmethod
    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """獲取特定交易對的最新價格資訊"""
        pass

    @abstractmethod
    def create_order(self, symbol: str, order_type: str, side: str, amount: float, price: float = None, params: Dict[str, Any] = {}) -> Dict[str, Any]:
        """建立訂單 (市價/限價/止損等)"""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """取消訂單"""
        pass

    @abstractmethod
    def get_open_orders(self, symbol: str = None) -> List[Dict[str, Any]]:
        """獲取當前掛單中的訂單"""
        pass

    @abstractmethod
    def get_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """獲取特定訂單的詳細狀態"""
        pass

    @property
    @abstractmethod
    def exchange_id(self) -> str:
        """回傳交易所標識符 (如 'binance')"""
        pass
