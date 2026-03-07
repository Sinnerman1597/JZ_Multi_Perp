from typing import Dict, Optional, List
from src.adapters.ccxt_adapter import CCXTAdapter
from rich.console import Console

console = Console()

# 判斷 API Key 是否為佔位符（未填入真實值）
_PLACEHOLDER_KEYWORDS = ("YOUR_", "您的", "...")

def _is_valid_api_key(key: str) -> bool:
    if not key:
        return False
    return not any(placeholder in str(key) for placeholder in _PLACEHOLDER_KEYWORDS)


class ExchangeRouter:
    """
    多交易所路由器 (AdTrack 策略專用)。
    依 fallback_order 依序初始化所有有效交易所，
    並在收到訊號時為指定幣種挑選「槓桿支援最接近訊號要求」的最佳交易所。
    """

    def __init__(self, exchange_config: Dict):
        self._adapters: Dict[str, CCXTAdapter] = {}  # {exchange_id: adapter}
        self._fallback_order: List[str] = exchange_config.get('fallback_order', [])
        self._initialize_all(exchange_config)

    def _initialize_all(self, config: Dict) -> None:
        """初始化所有已填入 API Key 的交易所，跳過佔位符或缺少 Key 的所。"""
        for ex_id in self._fallback_order:
            ex_cfg = config.get(ex_id, {})
            api_key = ex_cfg.get('apiKey', '')
            secret = ex_cfg.get('secret', '')

            # 跳過沒有填入真實 API Key 的交易所
            if not (_is_valid_api_key(api_key) and _is_valid_api_key(secret)):
                console.print(f"[dim][Router] 跳過 {ex_id}：未填入有效 API Key[/dim]")
                continue

            try:
                adapter = CCXTAdapter()
                # 提供 active 讓 CCXTAdapter 知道要初始化哪個所
                mock_cfg = dict(config)
                mock_cfg['active'] = ex_id
                adapter.initialize(mock_cfg)
                adapter._exchange.load_markets()
                self._adapters[ex_id] = adapter
                console.print(f"[green][Router] ✔ {ex_id} 初始化成功[/green]")
            except Exception as e:
                console.print(f"[yellow][Router] ⚠️ {ex_id} 初始化失敗，跳過：{e}[/yellow]")

    @property
    def primary_exchange(self) -> Optional[CCXTAdapter]:
        """回傳優先序第一個成功初始化的交易所（作為預設）"""
        for ex_id in self._fallback_order:
            if ex_id in self._adapters:
                return self._adapters[ex_id]
        return None

    def select_best_exchange(self, symbol: str, target_leverage: int) -> Optional[CCXTAdapter]:
        """
        選出最適合的交易所：
        1. 必須有此幣種
        2. 在有此幣種的交易所中，優先選 max_leverage >= target_leverage 的
        3. 若都不夠，選 max_leverage 最高的
        4. 若有多個都達標，依 fallback_order 優先序取第一個（leverage 相同時 bybit 優先）
        """
        candidates = []

        for ex_id in self._fallback_order:
            adapter = self._adapters.get(ex_id)
            if not adapter:
                continue
            if not adapter.has_symbol(symbol):
                console.print(f"[dim][Router] {ex_id} 無此幣種 {symbol}，跳過[/dim]")
                continue
            max_lev = adapter.get_max_leverage(symbol)
            candidates.append((ex_id, adapter, max_lev))
            console.print(f"[dim][Router] {ex_id} 支援 {symbol}，最大槓桿: {max_lev}X[/dim]")

        if not candidates:
            console.print(f"[red][Router] 無任何交易所支援 {symbol}，無法下單[/red]")
            return None

        # 優先挑 max_leverage >= target_leverage 的，且在優先序中最靠前的
        qualified = [(ex_id, adapter, lev) for ex_id, adapter, lev in candidates if lev >= target_leverage]
        if qualified:
            # 在達標的裡，依 fallback_order 已排好順序，取第一個
            best_id, best_adapter, best_lev = qualified[0]
        else:
            # 都不夠，退而求其次：選 max_leverage 最高的
            candidates.sort(key=lambda x: x[2], reverse=True)
            best_id, best_adapter, best_lev = candidates[0]

        console.print(f"[cyan][Router] 選定交易所: {best_id} (max_leverage={best_lev}X → 目標={target_leverage}X)[/cyan]")
        return best_adapter

    def get_all_open_symbols(self) -> set:
        """跨所查詢所有持倉幣種（用於避免重複進場）"""
        open_symbols = set()
        for ex_id, adapter in self._adapters.items():
            try:
                positions = adapter.get_open_positions()
                for pos in positions:
                    sym = pos.get('symbol', '')
                    if sym:
                        open_symbols.add(sym)
            except Exception:
                pass
        return open_symbols
