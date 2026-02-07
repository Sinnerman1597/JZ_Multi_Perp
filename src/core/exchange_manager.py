from typing import Dict, Any
from src.core.interfaces.exchange_abc import ExchangeInterface
from src.adapters.ccxt_adapter import CCXTAdapter

class ExchangeManager:
    """
    交易所管理器 (工廠類別)。
    負責根據配置類型實例化正確的適配器。
    """

    @staticmethod
    def create_exchange(config: Dict[str, Any]) -> ExchangeInterface:
        """
        根據配置中的 'active' 交易所及其 'type' 來建立對象。
        """
        active_id_raw = config.get('active')
        if not active_id_raw:
            raise ValueError("配置中缺少 'exchange.active'")

        # 自動轉小寫，增加容錯性 (例如 "BYBIT" -> "bybit")
        active_id = active_id_raw.lower()
        
        # 遍歷配置尋找匹配的 key (忽略大小寫)
        exchange_cfg = None
        target_key = None
        for key in config.keys():
            if key.lower() == active_id:
                exchange_cfg = config[key]
                target_key = key
                break

        if not exchange_cfg:
            raise ValueError(f"找不到 '{active_id_raw}' 的詳細配置資訊，請確認 YAML 中有定義此區塊")
        
        # 更新配置中的 active 為標準化的 key，確保後續適配器讀取一致
        effective_config = config.copy()
        effective_config['active'] = target_key

        exchange_type = exchange_cfg.get('type', 'ccxt').lower()

        # 分流邏輯：
        if exchange_type == 'ccxt':
            adapter = CCXTAdapter()
            adapter.initialize(effective_config)
            return adapter
        
        elif exchange_type == 'dex':
            # 未來在此處對接 DEXAdapter
            raise NotImplementedError("目前尚未實作 DEX 適配器")
            
        elif exchange_type == 'custom':
            # 未來在此處對接您的自定義適配器
            raise NotImplementedError("目前尚未實作 Custom 適配器")
            
        else:
            raise ValueError(f"不支緩的交易所類型: {exchange_type}")
