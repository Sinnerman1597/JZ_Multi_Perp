import ccxt
from typing import Dict, Any, List
from src.core.interfaces.exchange_abc import ExchangeInterface

class CCXTAdapter(ExchangeInterface):
    """
    CCXT 交易所適配器。
    將 CCXT 的 Unified API 封裝進系統定義的 ExchangeInterface。
    """

    def __init__(self):
        self._exchange: ccxt.Exchange = None
        self._exchange_name: str = ""

    def initialize(self, config: Dict[str, Any]) -> None:
        """
        根據配置動態初始化 CCXT 交易所實例。
        config 應包含: 'active' (交易所 ID) 以及對應的權限金鑰。
        """
        exchange_id = config.get('active')
        if not exchange_id:
            raise ValueError("配置中缺少 'exchange.active' 項")

        exchange_config = config.get(exchange_id, {})
        
        # 動態獲取 CCXT 中的交易所類別 (例如 ccxt.binance)
        try:
            exchange_class = getattr(ccxt, exchange_id)
        except AttributeError:
            raise ValueError(f"CCXT 不支援此交易所: {exchange_id}")

        # 實例化交易所並帶入配置
        self._exchange = exchange_class({
            'apiKey': exchange_config.get('apiKey'),
            'secret': exchange_config.get('secret'),
            'enableRateLimit': exchange_config.get('enableRateLimit', True),
            'options': exchange_config.get('options', {})
        })
        self._exchange_name = exchange_id
        
        # 測試連線 (選配：加載市場資訊以驗證 API)
        # self._exchange.load_markets()

    def get_balance(self) -> Dict[str, Any]:
        """獲取帳戶餘額"""
        if not self._exchange:
            raise RuntimeError("交易所尚未初始化")
        return self._exchange.fetch_balance()

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """獲取行情價格"""
        return self._exchange.fetch_ticker(symbol)

    def create_order(self, symbol: str, order_type: str, side: str, amount: float, price: float = None, params: Dict[str, Any] = {}) -> Dict[str, Any]:
        """建立訂單"""
        # CCXT 的 create_order 本身就是統一接口
        return self._exchange.create_order(symbol, order_type, side, amount, price, params)

    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """取消訂單"""
        self._exchange.cancel_order(order_id, symbol)
        return True

    def get_open_orders(self, symbol: str = None) -> List[Dict[str, Any]]:
        """獲取掛單清單"""
        return self._exchange.fetch_open_orders(symbol)

    @property
    def exchange_id(self) -> str:
        """獲取當前交易所 ID (字串)"""
        return self._exchange_name
