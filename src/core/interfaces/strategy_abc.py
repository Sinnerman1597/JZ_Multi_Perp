from abc import ABC, abstractmethod
from typing import Dict, Any

class StrategyInterface(ABC):
    """
    策略抽象基類 (Interface)。
    所有交易策略必須繼承並實作此類別。
    """

    @abstractmethod
    def on_init(self, params: Dict[str, Any]) -> None:
        """策略初始化邏輯，載入指標參數等"""
        pass

    @abstractmethod
    def on_tick(self, data: Dict[str, Any]) -> None:
        """當獲取新行情數據時觸發 (主動式策略)"""
        pass

    @abstractmethod
    def on_signal(self, signal_data: Dict[str, Any]) -> None:
        """當接收到外部訊號時觸發 (被動式/訊號驅動策略)"""
        pass

    @property
    @abstractmethod
    def requirements(self) -> Dict[str, Any]:
        """
        宣告此策略需要的參數清單。
        CLI 會根據此屬性能實現上下文感知配置。
        """
        pass

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """回傳策略名稱"""
        pass
