from typing import Dict, Any
from src.core.strategy_base import StrategyBase

class DemoSignalStrategy(StrategyBase):
    """
    示範策略：專門處理外部訊號。
    這是一個被動式策略，用於展示訊號如何觸發交易。
    """

    def on_tick(self, data: Dict[str, Any]) -> None:
        """訊號策略通常不主動跑指標"""
        pass

    def on_signal(self, signal_data: Dict[str, Any]) -> None:
        """接收到解析後的訊號，執行交易"""
        symbol = signal_data.get("symbol")
        side = signal_data.get("side")
        price = signal_data.get("entry_price")
        
        print(f"[Strategy: {self.strategy_name}] 接收到解析訊號，準備執行...")
        
        # 調用 StrategyBase 封裝的下單方法
        self.execute_trade(
            symbol=symbol,
            side=side,
            amount=0.01, # 這裡未來應由風控模組計算
            price=price
        )

    @property
    def requirements(self) -> Dict[str, Any]:
        """宣告僅需要全局最大倉位限制"""
        return {
            "max_pos_per_trade": {"type": "float", "description": "單筆最大下單量", "default": 0.1}
        }

    @property
    def strategy_name(self) -> str:
        return "demo_signal_strategy"
