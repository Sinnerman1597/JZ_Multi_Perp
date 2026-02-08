import re
from typing import Dict, Any, Optional
from src.core.interfaces.parser_abc import ParserInterface

class ItalyParser(ParserInterface):
    """
    Italy_Channel 專用解析器 (英文格式)。
    特點：解析英文關鍵字，並標記 force_market = True。
    """

    def parse(self, raw_message: str) -> Optional[Dict[str, Any]]:
        if not isinstance(raw_message, str):
            return None

        # 1. 提取幣對 (例如: MORPHO/USDT)
        symbol_match = re.search(r"^([A-Z0-9/]+)", raw_message, re.M)
        if not symbol_match:
            return None
        
        symbol_raw = symbol_match.group(1).replace("/", "")
        symbol = f"{symbol_raw[:-4]}/{symbol_raw[-4:]}:USDT" # 轉為 CCXT Bybit 格式

        # 2. 提取方向 (LONG/SHORT)
        side_match = re.search(r"(LONG|SHORT|BUY|SELL)", raw_message, re.I)
        side_val = side_match.group(1).upper() if side_match else ""
        side = 'buy' if side_val in ["LONG", "BUY"] else 'sell'

        # 3. 提取槓桿 (例如: Cross 20x)
        leverage_match = re.search(r"(\d+)x", raw_message, re.I)
        leverage = int(leverage_match.group(1)) if leverage_match else 1

        # 4. 提取進場區間 (雖然要市價，但仍解析出來備用)
        # 格式: 1.2168/1.2446
        entry_match = re.search(r"Entry Zone:\s*([\d\.]+)/([\d\.]+)", raw_message, re.I)
        entry_min = entry_max = 0.0
        if entry_match:
            prices = [float(entry_match.group(1)), float(entry_match.group(2))]
            entry_min, entry_max = min(prices), max(prices)

        # 5. 提取止損 (有些英文訊號會寫 SL: 或 Stop Loss:)
        sl_match = re.search(r"(?:SL|Stop Loss):\s*([\d\.]+)", raw_message, re.I)
        stop_loss = float(sl_match.group(1)) if sl_match else None
        
        # 如果訊號中沒有 SL，根據方向給予一個極遠的預設值或從配置讀取 (此處設為 None 讓策略處理)

        # 6. 提取止盈 (TP1, TP2...)
        tp_matches = re.findall(r"TP\d+:\s*([\d\.]+)", raw_message, re.I)
        take_profits = [float(tp) for tp in tp_matches]

        return {
            "symbol": symbol,
            "side": side,
            "leverage": leverage,
            "entry_min": entry_min,
            "entry_max": entry_max,
            "stop_loss": stop_loss,
            "take_profits": take_profits,
            "force_market": True, # <--- 核心優化：標記此訊號需強制市價執行
            "raw_text": raw_message
        }

    @property
    def source_name(self) -> str:
        return "italy_parser"
