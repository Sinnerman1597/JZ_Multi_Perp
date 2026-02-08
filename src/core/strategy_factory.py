from typing import Dict, Any, Type, List
from src.core.interfaces.strategy_abc import StrategyInterface
from src.strategies.demo_ma_crossover import DemoMACrossover
from src.strategies.demo_signal_strategy import DemoSignalStrategy
from src.strategies.adtrack_strategy import AdTrack

class StrategyFactory:
    """策略工廠：負責管理與實例化交易策略"""
    
    # 註冊表：將配置字串映射到具體類別
    _REGISTERED_STRATEGIES = {
        "demo_ma_crossover": DemoMACrossover,
        "demo_signal_strategy": DemoSignalStrategy,
        "AdTrack": AdTrack,
    }

    @classmethod
    def get_available_strategies(cls) -> List[str]:
        """回傳目前所有註冊的策略名稱列表"""
        return list(cls._REGISTERED_STRATEGIES.keys())

    @classmethod
    def create_strategy(cls, name: str, exchange: Any) -> StrategyInterface:
        """根據名稱實例化策略"""
        strategy_class = cls._REGISTERED_STRATEGIES.get(name)
        if not strategy_class:
            raise ValueError(f"找不到策略: {name}")
        return strategy_class(exchange)
