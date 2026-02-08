from typing import Dict, Any, List
from src.core.interfaces.exchange_abc import ExchangeInterface
from src.core.interfaces.strategy_abc import StrategyInterface
from src.infrastructure.message_parsers.parser_factory import ParserFactory

class StrategyEngine:
    """
    策略引擎 (核心調度器)。
    負責協調交易所、策略與多個訊號來源。
    """

    def __init__(self, exchange: ExchangeInterface):
        self.exchange = exchange
        self.active_strategies: List[StrategyInterface] = []
        self.parsers: Dict[str, Any] = {} 
        self.is_running = False
        self.stats = {
            "total_signals": 0,
            "executed_trades": 0,
            "last_signal_time": "None",
            "status": "等待連線...",
            "message_logs": [],   # 存儲最近 5 則訊息內容
            "active_trades": []   # 存儲當前執行的策略持倉狀態
        }

    def add_strategy(self, strategy: StrategyInterface, params: Dict[str, Any]):
        """註冊並初始化策略"""
        strategy.engine = self  # 注入引擎實例以便策略更新數據
        strategy.on_init(params)
        self.active_strategies.append(strategy)

    def setup_signal_sources(self, signal_config: Dict[str, Any]):
        """根據配置初始化多個訊號解析器"""
        if not signal_config.get('enabled', False):
            return

        sources = signal_config.get('sources', [])
        for src in sources:
            name = src.get('name')
            parser_name = src.get('parser')
            parser_instance = ParserFactory.create_parser(parser_name)
            
            if parser_instance:
                self.parsers[name] = parser_instance
                print(f"[Engine] 已啟動訊號源監控: {name} (使用解析器: {parser_name})")

    def process_incoming_message(self, source_name: str, raw_message: Any):
        """
        處理傳入的原始訊息 (由 SignalReceiver 呼叫)。
        """
        parser = self.parsers.get(source_name)
        if not parser:
            return

        trade_signal = parser.parse(raw_message)
        
        # 更新統計數據
        self.stats["total_signals"] += 1
        from datetime import datetime
        now_time = datetime.now().strftime("%H:%M:%S")
        self.stats["last_signal_time"] = now_time
        
        # 紀錄日誌 (僅保存最近 5 條)
        log_entry = f"[{now_time}] {source_name}: {raw_message}"
        self.stats["message_logs"].insert(0, log_entry)
        self.stats["message_logs"] = self.stats["message_logs"][:5]

        if trade_signal:
            print(f"[Engine] 從 {source_name} 獲取到有效交易訊號，正在分發...")
            self.stats["executed_trades"] += 1
            for strategy in self.active_strategies:
                strategy.on_signal(trade_signal)

    def run_tick(self, market_data: Dict[str, Any]):
        """驅動主動型策略"""
        for strategy in self.active_strategies:
            strategy.on_tick(market_data)
