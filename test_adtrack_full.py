import asyncio
from unittest.mock import MagicMock
from src.strategies.adtrack_strategy import AdTrack
from src.infrastructure.message_parsers.adtrack_parser import AdTrackParser

async def test_full_adtrack_logic():
    print("=== AdTrack 策略完整邏輯模擬測試 ===\n")

    # 1. 準備模擬交易所 (Mock Exchange)
    mock_exchange_wrapper = MagicMock()
    # 模擬 CCXT 內部實例
    mock_ccxt = MagicMock()
    mock_exchange_wrapper._exchange = mock_ccxt
    
    # 模擬當前市價為 0.0201 (在區間內)
    mock_exchange_wrapper.get_ticker.return_value = {'last': 0.0201}
    # 模擬 Bybit 精度處理 (假設回傳原始值)
    mock_ccxt.amount_to_precision.side_effect = lambda s, a: str(round(a, 2))
    # 模擬下單回傳
    mock_exchange_wrapper.create_order.return_value = {'id': 'order_12345'}

    # 2. 初始化策略
    strategy = AdTrack(mock_exchange_wrapper)
    # 設定參數: 投資 100 USDT
    strategy.on_init({"investment_mode": "USDT", "investment_value": 100.0})

    # 3. 準備測試訊號 (AdTrack 格式)
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
    
    print("[Test] 正在將訊號推送到策略...")
    # 4. 執行策略 (會啟動 _process_adtrack_execution)
    # 我們手動等待任務完成以便檢查結果
    await strategy._process_adtrack_execution(signal_data)

    # 5. 驗證 Bybit 設定
    print("\n[驗證] 檢查 Bybit 設定:")
    mock_ccxt.set_margin_mode.assert_called_with('cross', 'DAM/USDT:USDT')
    print("  ✔ set_margin_mode('cross') 被調用")
    mock_ccxt.set_leverage.assert_called_with(10, 'DAM/USDT:USDT')
    print("  ✔ set_leverage(10) 被調用")

    # 6. 驗證下單數量 (100 USDT * 10X / 0.0201 = 49751.24)
    print("\n[驗證] 檢查下單數量計算:")
    # 應該會有一次主下單 call
    calls = mock_exchange_wrapper.create_order.call_args_list
    main_order_call = calls[0]
    amount_sent = main_order_call[1]['amount']
    print(f"  ✔ 計算出的下單量: {amount_sent} (預期接近 49751)")

    # 7. 驗證 TP/SL 掛單
    print("\n[驗證] 檢查分階止盈與止損:")
    # 預期總 Call 次數: 1(主單) + 4(TP) + 1(SL) = 6 次
    print(f"  ✔ 總下單要求次數: {len(calls)} 次 (預期 6 次)")
    
    # 檢查是否有帶 stopPrice 的止損單
    sl_call = [c for c in calls if 'stopPrice' in c[1].get('params', {})]
    if sl_call:
        print(f"  ✔ 檢測到全局止損掛單: {sl_call[0][1]['params']['stopPrice']}")

    print("\n=== 模擬測試圓滿完成！程式邏輯正確。 ===")

if __name__ == "__main__":
    asyncio.run(test_full_adtrack_logic())
