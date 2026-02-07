import re
from typing import Dict, Any, Optional, List
from src.core.interfaces.parser_abc import ParserInterface

class AdTrackParser(ParserInterface):
    """
    AdTrack 專用解析器。
    解析 Telegram 頻道發送的固定格式交易訊號。
    """

    def parse(self, raw_message: str) -> Optional[Dict[str, Any]]:
        if not isinstance(raw_message, str):
            return None

        # 預處理：移除所有 Emoji 和特殊符號，只保留文字與數字
        # [^\u4e00-\u9fa5^a-z^A-Z^0-9^\s^:^：^.^-] 代表排除掉 中文/英文/數字/空白/冒號/點/橫槓 以外的字元
        clean_text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s:：\.\-]', '', raw_message)
        
        # 使用過濾後的文字進行匹配
        # 1. 提取幣對 (例如: DAMUSDT)
        symbol_match = re.search(r"交易對：\s*([A-Z0-9]+)", clean_text)
        if not symbol_match:
            return None # 非 AdTrack 格式訊息
        
        symbol_raw = symbol_match.group(1)
        # 轉換為標準格式 (例如 DAM/USDT:USDT)
        # Bybit 永續合約在 CCXT 通常使用 Symbol/USDT:USDT 格式
        symbol = f"{symbol_raw[:-4]}/{symbol_raw[-4:]}:USDT" if symbol_raw.endswith("USDT") else symbol_raw

        # 2. 提取方向 (LONG/SHORT)
        side_match = re.search(r"倉位：\s*(SHORT|LONG)", clean_text, re.IGNORECASE)
        side = side_match.group(1).lower() if side_match else None
        # 轉為 CCXT 標準 side: 'buy' 或 'sell'
        execution_side = 'sell' if side == 'short' else 'buy'

        # 3. 提取槓桿 (例如: 6X)
        leverage_match = re.search(r"槓桿倍數：\s*(\d+)", clean_text)
        leverage = int(leverage_match.group(1)) if leverage_match else 1

        # 4. 提取進場區間 (例如: 0.02003-0.02023)
        entry_match = re.search(r"進場區域：\s*([\d\.]+)-([\d\.]+)", clean_text)
        entry_min = None
        entry_max = None
        if entry_match:
            # 確保 p1 是小值，p2 是大值
            p1 = float(entry_match.group(1))
            p2 = float(entry_match.group(2))
            entry_min = min(p1, p2)
            entry_max = max(p1, p2)

        # 5. 提取止損 (SL)
        sl_match = re.search(r"止損：\s*([\d\.]+)", clean_text)
        stop_loss = float(sl_match.group(1)) if sl_match else None

        # 6. 提取多個止盈目標 (TP)
        # 查找所有數字標註的目標值
        tp_matches = re.findall(r"目標\d+：\s*([\d\.]+)", clean_text)
        take_profits = [float(tp) for tp in tp_matches]

        return {
            "symbol": symbol,
            "side": execution_side,
            "leverage": leverage,
            "entry_min": entry_min,
            "entry_max": entry_max,
            "stop_loss": stop_loss,
            "take_profits": take_profits,
            "raw_text": raw_message
        }

    @property
    def source_name(self) -> str:
        return "adtrack_parser"
