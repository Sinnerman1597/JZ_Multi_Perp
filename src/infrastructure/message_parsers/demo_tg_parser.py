import re
from typing import Dict, Any, Optional
from src.core.interfaces.parser_abc import ParserInterface

class DemoTGParser(ParserInterface):
    """
    示範解析器：Telegram 訊號解析。
    範例格式: "Long BTCUSDT entry 95000 sl 92000"
    """

    def parse(self, raw_message: str) -> Optional[Dict[str, Any]]:
        if not isinstance(raw_message, str):
            return None

        # 簡單的正則匹配範例 (僅作展示)
        pattern = r"(BUY|SELL|LONG|SHORT)\s+([A-Z]+)\s+entry\s+([\d\.]+)"
        match = re.search(pattern, raw_message, re.IGNORECASE)

        if match:
            side_raw = match.group(1).lower()
            return {
                "symbol": f"{match.group(2).upper()}/USDT",
                "side": "buy" if side_raw in ["buy", "long"] else "sell",
                "entry_price": float(match.group(3)),
                "raw_source": raw_message
            }
        
        return None

    @property
    def source_name(self) -> str:
        return "demo_telegram_parser"
