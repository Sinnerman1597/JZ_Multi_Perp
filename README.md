# Multi_Base 🚀
> 一個基於 Python 的可插拔量化交易框架。

Multi_Base 是一個設計精美且高度模組化的交易系統，支援 CCXT 旗下的多個交易所、去中心化交易所（DEX）以及外部訊號（Telegram/TradingView）跟單。

## ✨ 特色
- **可插拔適配器 (Pluggable Adapters)**：輕鬆切換 CEX 與 DEX。
- **雙驅動模式**：支援「自主指標策略」與「外部訊號驅動」兩種執行模式。
- **上下文感知 CLI**：專業的互動式啟動介面。
- **多頻道訊號分發**：可同時監控多個 Telegram 頻道並使用不同的解析器。
- **Clean Code 架構**：遵循 SOLID 與 DIP 原則，模組極易遷移。

## 🛠 安裝步驟

1. **複製專案**
   ```bash
   git clone https://github.com/yourusername/Multi_Base.git
   cd Multi_Base
   ```

2. **建立虛擬環境**
   ```bash
   python -m venv venv
   source venv/bin/scripts/activate  # Windows: venv\Scripts\activate
   ```

3. **安裝依賴**
   ```bash
   pip install -r requirements.txt
   ```

4. **配置系統**
   將 `config.yaml.example` 複製為 `config.yaml` 並填入您的 API Key。
   ```bash
   cp config.yaml.example config.yaml
   ```

## 🚀 快速啟動
執行主程式進入互動式選單：
```bash
python main.py
```

## 📂 目錄結構
- `src/core`：系統核心邏輯與介面定義。
- `src/adapters`：交易所適配器實作。
- `src/strategies`：交易策略庫。
- `src/cli`：互動式控制介面。
- `src/ui`：視覺化監控面板。

## 📜 授權
MIT License.
