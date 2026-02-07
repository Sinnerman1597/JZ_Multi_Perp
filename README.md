# JZ_Multi_Perp 🚀
> 一個基於 Python 的可插拔量化交易框架。

JZ_Multi_Perp 是一個高度模組化的交易系統，支援 CCXT 旗下的多個交易所、Telegram 訊號跟單及視覺化監控。

## ✨ 特色
- **AdTrack 深度整合**：專為 AdTrack 訊號設計的解析器與 Bybit 執行策略。
- **階梯止盈系統**：自動部署 4 級 (25% 減倉) 止盈單。
- **動態移動止損**：當達成 TP1、TP2 時，自動將止損位移至本金位或前一目標位。
- **可插拔適配器**：輕鬆切換 CEX 與自定義交易所。
- **雙驅動模式**：支援「自主指標策略」與「外部訊號驅動」兩種執行模式。
- **上下文感知 CLI**：具備非同步監聽能力的互動式啟動介面。

## 🛠 安裝步驟

1. **建立環境**
   ```bash
   python -m venv .venv
   # Windows
   .\.venv\Scripts\activate
   ```

2. **安裝依賴**
   ```bash
   pip install -r requirements.txt
   ```

3. **配置系統與 Session 移植**
   - 將 `config.yaml.example` 複製為 `config.yaml` 並填入 API Key 與 Telegram API ID/Hash。
   - **Session 移植**：如果您已有已登入的 `.session` 檔案，請將其放入根目錄，並在 `config.yaml` 設定對應的 `session_name` 以跳過登入驗證。

## 🚀 快速啟動
執行主程式進入互動式選單：
```bash
python main.py
```

## 📂 目錄結構
- `src/core`：系統核心邏輯、介面定義與策略基類。
- `src/adapters`：交易所適配器 (如 CCXTAdapter)。
- `src/strategies`：交易策略庫 (包含 AdTrack)。
- `src/infrastructure`：訊息解析器與 Telegram 接收端。
- `src/ui` & `src/cli`：Dashboard 與互動式選單。

## 📜 授權
MIT License.
