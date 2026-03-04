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

        # 1. 識別動作類型 (進場、單筆平倉、批量平倉)
        raw_lower = raw_message.lower()
        if "close all" in raw_lower:
            side_match = re.search(r"(LONG|SHORT)", raw_lower, re.I)
            if side_match:
                # 注意：指令中的 Short 代表要關閉空單 (原本進場 side 是 'sell')
                target_side = 'buy' if side_match.group(1).upper() == 'LONG' else 'sell'
                return {
                    "action": "exit_all",
                    "target_side": target_side,
                    "raw_text": raw_message
                }

        is_exit_signal = "closing here" in raw_lower
        action = "exit" if is_exit_signal else "entry"

        # 2. 提取幣對 (例如: MORPHO/USDT)
        # 如果是平倉訊號且當前行沒幣種，會透過 [REPLY_TO] 後面的內容補償
        symbol_match = re.search(r"([A-Z0-9/]+)(?:/USDT|\s+LONG|\s+SHORT)", raw_message, re.I)
        if not symbol_match:
            return None
        
        symbol_raw = symbol_match.group(1).replace("/", "").upper()
        # 處理 CCXT Bybit 格式 (支援 5 夾 4 字元規則)
        if len(symbol_raw) > 4:
            symbol = f"{symbol_raw[:-4]}/{symbol_raw[-4:]}:USDT"
        else:
            symbol = f"{symbol_raw}/USDT:USDT"

        if action == "exit":
            return {
                "action": "exit",
                "symbol": symbol,
                "raw_text": raw_message
            }

        # --- 以下為進場訊號專用解析 ---
        # 3. 提取方向 (LONG/SHORT)
        side_match = re.search(r"(LONG|SHORT|BUY|SELL)", raw_message, re.I)
        side_val = side_match.group(1).upper() if side_match else ""
        side = 'buy' if side_val in ["LONG", "BUY"] else 'sell'

        # 4. 提取槓桿
        leverage_match = re.search(r"(\d+)x", raw_message, re.I)
        leverage = int(leverage_match.group(1)) if leverage_match else 1

        # 5. 提取止盈
        tp_matches = re.findall(r"TP\d+:\s*([\d\.]+)", raw_message, re.I)
        take_profits = [float(tp) for tp in tp_matches]

        # 6. 提取止損
        sl_match = re.search(r"(?:SL|Stop Loss):\s*([\d\.]+)", raw_message, re.I)
        stop_loss = float(sl_match.group(1)) if sl_match else None

        return {
            "action": "entry",
            "symbol": symbol,
            "side": side,
            "leverage": leverage,
            "stop_loss": stop_loss,
            "take_profits": take_profits,
            "force_market": True,
            "raw_text": raw_message
        }

    @property
    def source_name(self) -> str:
        return "italy_parser"
