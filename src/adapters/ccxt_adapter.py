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

    def initialize(self, config: Dict[str, Any]):
        """初始化交易所"""
        exchange_id = config.get('active', 'bybit').lower()
        self._exchange_name = exchange_id  # 紀錄交易所 ID
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

        # 如果設定中開啟了 sandbox 模式，則切換到模擬網 (Testnet)
        if exchange_config.get('sandbox', False):
            self._exchange.set_sandbox_mode(True)
            print(f"[Exchange] {exchange_id} 已啟動模擬網 (Sandbox) 模式")
        self._exchange_name = exchange_id
        
        # 測試連線 (選配：加載市場資訊以驗證 API)
        # self._exchange.load_markets()

    def get_balance(self) -> Dict[str, Any]:
        """獲取帳戶餘額"""
        if not self._exchange:
            raise RuntimeError("交易所尚未初始化")
        return self._exchange.fetch_balance()

    def has_symbol(self, symbol: str) -> bool:
        """檢查此交易所是否支援該交易對"""
        try:
            if not self._exchange.markets:
                self._exchange.load_markets()
            return symbol in self._exchange.markets
        except Exception:
            return False

    def get_max_leverage(self, symbol: str) -> int:
        """查詢該交易對的最大槓桿倍數，無法取得時回傳 1"""
        try:
            if not self._exchange.markets:
                self._exchange.load_markets()
            market = self._exchange.markets.get(symbol, {})
            # CCXT 標準欄位
            limits = market.get('limits', {})
            lev_limit = limits.get('leverage', {})
            max_lev = lev_limit.get('max')
            if max_lev:
                return int(max_lev)
            # 備用：部分交易所放在 info 裡
            info = market.get('info', {})
            for key in ('maxLeverage', 'max_leverage', 'leverageFilter'):
                if key in info:
                    val = info[key]
                    if isinstance(val, dict):
                        val = val.get('maxLeverage') or val.get('max') or 1
                    return int(float(val))
            return 1
        except Exception:
            return 1

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """獲取當前所有持倉（開放倉位）"""
        try:
            positions = self._exchange.fetch_positions()
            # 只回傳有真實倉位的（contracts > 0）
            return [p for p in positions if abs(float(p.get('contracts') or 0)) > 0]
        except Exception:
            return []

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """獲取行情價格"""
        if not self._exchange.markets:
            self._exchange.load_markets()
        return self._exchange.fetch_ticker(symbol)

    def set_leverage(self, leverage: int, symbol: str) -> Dict[str, Any]:
        """設定槓桿 (處理型別與格式)"""
        if not self._exchange:
            raise RuntimeError("交易所尚未初始化")
        
        # 確保市場資料已加載 (同步)
        if not self._exchange.markets:
            self._exchange.load_markets()
        
        # 強制轉為整數
        lv = int(leverage)
        return self._exchange.set_leverage(lv, symbol)

    def create_order(self, symbol: str, order_type: str, side: str, amount: float, price: float = None, params: Dict[str, Any] = {}) -> Dict[str, Any]:
        """建立訂單"""
        if not self._exchange:
            raise RuntimeError("交易所尚未初始化")
            
        # 確保市場資料已加載 (同步)
        if not self._exchange.markets:
            self._exchange.load_markets()
        
        return self._exchange.create_order(symbol, order_type, side, amount, price, params)

    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """取消訂單"""
        if not self._exchange.markets:
            self._exchange.load_markets()
        self._exchange.cancel_order(order_id, symbol)
        return True

    def get_open_orders(self, symbol: str = None) -> List[Dict[str, Any]]:
        """獲取掛單清單"""
        if not self._exchange.markets:
            self._exchange.load_markets()
        return self._exchange.fetch_open_orders(symbol)

    def get_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """獲取特定訂單詳細資訊 (加入 Bybit 多重歷史回溯邏輯)"""
        if not self._exchange.markets:
            self._exchange.load_markets()
        
        try:
            return self._exchange.fetch_order(order_id, symbol)
        except Exception as e:
            err_msg = str(e).lower()
            # 針對 Bybit V5 的各種「查不到單」錯誤進行深度回溯
            if any(x in err_msg for x in ["last 500 orders", "not found", "invalid orderid"]):
                try:
                    # 1. 第一層回溯：歷史訂單庫 (fetchClosedOrders)
                    closed_orders = self._exchange.fetch_closed_orders(symbol, limit=50)
                    for o in closed_orders:
                        if o['id'] == order_id: return o
                    
                    # 2. 第二層回溯：成交紀錄 (fetchMyTrades)
                    # 有時候成交編號和訂單編號在 API 表現上有重疊，或訂單已消失但成交還在
                    trades = self._exchange.fetch_my_trades(symbol, limit=50)
                    for t in trades:
                        if t['order'] == order_id or t['id'] == order_id:
                            # 構造一個模擬的 order 物件
                            return {
                                'id': order_id, 'symbol': symbol, 'status': 'closed',
                                'price': t['price'], 'amount': t['amount'], 'filled': t['amount']
                            }
                except: pass
            raise e

    def amount_to_precision(self, symbol: str, amount: float) -> str:
        """根據交易所精度格式化交易數量"""
        if not self._exchange.markets:
            self._exchange.load_markets()
        return self._exchange.amount_to_precision(symbol, amount)

    @property
    def exchange_id(self) -> str:
        """獲取當前交易所 ID (字串)"""
        return self._exchange_name
