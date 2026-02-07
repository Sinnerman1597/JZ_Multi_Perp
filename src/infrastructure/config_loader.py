import yaml
import os
from typing import Dict, Any

class ConfigLoader:
    """
    配置加載器 (優化版)。
    1. 支援 YAML 讀取。
    2. 支援環境變數覆蓋 (例如: EXCHANGE_ACTIVE)。
    3. 具備功能開關判斷。
    """
    
    _config: Dict[str, Any] = {}

    @classmethod
    def load_config(cls, config_path: str = "config.yaml") -> Dict[str, Any]:
        """從指定路徑讀取 YAML 設定檔，若不存在則回傳空字典"""
        if not os.path.exists(config_path):
            cls._config = {}
            return cls._config
        
        with open(config_path, 'r', encoding='utf-8') as f:
            cls._config = yaml.safe_load(f) or {}
        
        return cls._config

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """
        獲取配置值。
        順序：環境變數 (如 EXCHANGE_ACTIVE) > YAML 配置 > 預設值。
        """
        # 1. 檢查環境變數 (將 'exchange.active' 轉為 'EXCHANGE_ACTIVE')
        env_key = key.replace('.', '_').upper()
        env_value = os.getenv(env_key)
        if env_value is not None:
            return env_value

        # 2. 獲取 YAML 配置
        keys = key.split('.')
        value = cls._config
        try:
            for k in keys:
                value = value[k]
            return value if value is not None else default
        except (KeyError, TypeError):
            return default

    @classmethod
    def is_enabled(cls, feature_path: str) -> bool:
        """
        輔助方法：檢查某個功能是否啟動。
        範例：is_enabled('signals.telegram')
        """
        return bool(cls.get(f"{feature_path}.enabled", False))

    @classmethod
    def get_all(cls) -> Dict[str, Any]:
        """獲取全部配置"""
        return cls._config
