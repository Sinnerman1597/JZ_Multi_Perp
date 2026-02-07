from typing import Dict, Any
from src.core.strategy_base import StrategyBase

class DemoMACrossover(StrategyBase):
    """
    示範策略：均線交叉。
    這是一個主動式策略，用於展示如何宣告參數需求。
    """

    def on_tick(self, data: Dict[str, Any]) -> None:
        """主動輪詢行情時觸發"""
        # 這裡會放置指標計算與買賣邏輯
        pass

    def on_signal(self, signal_data: Dict[str, Any]) -> None:
        """此策略為主動型，通常不處理外部訊號"""
        pass

    @property
    def requirements(self) -> Dict[str, Any]:
        """
        關鍵點：向 CLI 宣告它需要哪些參數。
        """
        return {
            "symbol": {"type": "string", "description": "交易對 (如 BTC/USDT)", "required": True},
            "fast_period": {"type": "int", "description": "快線週期", "default": 10},
            "slow_period": {"type": "int", "description": "慢線週期", "default": 20},
            "leverage": {"type": "int", "description": "槓桿倍數", "default": 1}
        }

    @property
    def strategy_name(self) -> str:
        return "demo_ma_crossover"
