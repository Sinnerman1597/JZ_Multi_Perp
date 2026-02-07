from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class ParserInterface(ABC):
    """
    訊息解析器介面。
    負責將非結構化（文字）或半結構化（JSON）訊息轉化為系統可執行的指令。
    """

    @abstractmethod
    def parse(self, raw_message: Any) -> Optional[Dict[str, Any]]:
        """
        將原始訊息解析為統一的交易指令。
        回傳格式應包含: symbol, side, amount, entry_price, sl, tp 等。
        若解析失敗或非交易訊號，應回傳 None。
        """
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        """解析器的來源標識（如 'telegram_alpha_group'）"""
        pass
