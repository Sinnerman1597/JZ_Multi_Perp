from src.infrastructure.message_parsers.adtrack_parser import AdTrackParser
import json

def test_adtrack_parsing():
    print("=== AdTrack 解析器功能驗證 ===")
    
    # 模擬從截圖中提取的原始訊息
    raw_message = (
        "📈 交易對：DAMUSDT\n"
        "📊 倉位：SHORT\n"
        "💪 槓桿倍數：6X\n"
        "🔍 進場區域：0.02003-0.02023\n"
        "⛔ 止損：0.02684\n"
        "🎯 目標1：0.01993\n"
        "🎯 目標2：0.01973\n"
        "💎 目標3：0.01953\n"
        "🎯 目標4：0.01912"
    )

    parser = AdTrackParser()
    result = parser.parse(raw_message)

    if result:
        print("\n[OK] 解析成功！提取數據如下：")
        print("-" * 30)
        # 格式化輸出字典
        for key, value in result.items():
            if key != "raw_text":
                print(f"{key:15}: {value}")
        print("-" * 30)
        
        # 驗證特定欄位
        assert result['symbol'] == "DAM/USDT:USDT"
        assert result['side'] == "sell"
        assert result['leverage'] == 6
        assert len(result['take_profits']) == 4
        print("\n驗證點通過：幣對格式、方向、槓桿、止盈目標數量皆正確。")
    else:
        print("\n[Error] 解析失敗，請檢查正則表達式。")

if __name__ == "__main__":
    test_adtrack_parsing()
