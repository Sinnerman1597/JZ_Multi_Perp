import asyncio
from unittest.mock import MagicMock
from src.strategies.adtrack_strategy import AdTrack
from src.infrastructure.message_parsers.adtrack_parser import AdTrackParser

async def test_full_adtrack_logic_v2():
    print("=== AdTrack 策略 V4.1 深度邏輯測試 (狀態確認版) ===\n")

    # 1. 準備模擬交易所 (Mock Exchange)
    mock_exchange_wrapper = MagicMock()
    mock_ccxt = MagicMock()
    mock_exchange_wrapper._exchange = mock_ccxt
    
    # 基本設定回傳
    mock_exchange_wrapper.get_ticker.return_value = {'last': 0.0201}
    mock_ccxt.amount_to_precision.side_effect = lambda s, a: str(round(a, 2))
    
    # 模擬下單流水號
    order_counter = 0
    def mock_create_order(*args, **kwargs):
        nonlocal order_counter
        order_counter += 1
        return {'id': f'order_{order_counter}', 'status': 'open'}
    
    mock_exchange_wrapper.create_order.side_effect = mock_create_order

    # 2. 模擬 get_order 狀態轉換邏輯
    # 我們讓 TP1 訂單一開始是 open，第二次查詢變 closed
    order_states = {}
    def mock_get_order(order_id, symbol):
        if order_id not in order_states:
            order_states[order_id] = 'open'
        else:
            # 模擬第二次查詢時，訂單已成交
            order_states[order_id] = 'closed'
        return {'id': order_id, 'status': order_states[order_id]}

    mock_exchange_wrapper.get_order.side_effect = mock_get_order

    # 3. 初始化策略
    strategy = AdTrack(mock_exchange_wrapper)
    strategy.on_init({"investment_mode": "USDT", "investment_value": 100.0})

    # 4. 準備測試訊號
    raw_msg = (
        "📈 交易對：DAMUSDT\n"
        "📊 倉位：SHORT\n"
        "💪 槓桿倍數：10X\n"
        "🔍 進場區域：0.02000-0.02050\n"
        "⛔ 止損：0.02500\n"
        "🎯 目標1：0.01900\n"
        "🎯 目標2：0.01800\n"
        "🎯 目標3：0.01700\n"
        "🎯 目標4：0.01600"
    )
    
    parser = AdTrackParser()
    signal_data = parser.parse(raw_msg)
    
    print("[Test] 發送訊號...")
    await strategy._process_adtrack_execution(signal_data)

    # 5. 手動觸發一次監控檢查
    print("\n[Test] 第一次監控檢查 (訂單應均為 OPEN)...")
    await strategy._check_trade_update(strategy.watched_trades[0])
    
    print("[Test] 第二次監控檢查 (TP 訂單應切換為 CLOSED)...")
    # 此時 mock_get_order 會回傳 closed
    await strategy._check_trade_update(strategy.watched_trades[0])

    # 6. 驗證移動止損是否被調用
    # 如果移動止損有跑，create_order 的次數會增加 (原本 6 次 + 1 次 SL 移動)
    calls = mock_exchange_wrapper.create_order.call_args_list
    print(f"\n[驗證] 總下單要求次數: {len(calls)}")
    
    if len(calls) > 6:
        print("  ✔ 成功偵測到 TP 成交並發出「移動止損」指令！")
    else:
        print("  ✘ 未偵測到移動止損發出。")

    print("\n=== V4.1 邏輯測試完成 ===")

if __name__ == "__main__":
    asyncio.run(test_full_adtrack_logic_v2())
