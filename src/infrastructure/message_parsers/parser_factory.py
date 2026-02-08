from typing import Dict, Any, Optional, Type
from src.core.interfaces.parser_abc import ParserInterface
from src.infrastructure.message_parsers.demo_tg_parser import DemoTGParser
from src.infrastructure.message_parsers.adtrack_parser import AdTrackParser
from src.infrastructure.message_parsers.italy_parser import ItalyParser

class ParserFactory:
    """
    解析器工廠。
    根據名稱動態產生對應的解析器實例。
    """
    
    # 註冊表：將配置字串映射到具體類別
    _REGISTERED_PARSERS = {
        "demo_tg_parser": DemoTGParser,
        "adtrack_parser": AdTrackParser,
        "italy_parser": ItalyParser,
    }

    @classmethod
    def create_parser(cls, parser_name: str) -> Optional[ParserInterface]:
        """建立解析器實例"""
        parser_class = cls._REGISTERED_PARSERS.get(parser_name)
        if not parser_class:
            print(f"[Warning] 找不到名稱為 '{parser_name}' 的解析器，將無法處理該來源訊號")
            return None
        return parser_class()
