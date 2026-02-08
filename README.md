# JZ_Multi_Perp 🚀
> 一個基於 Python 的高度可插拔、模組化量化交易框架。

JZ_Multi_Perp 專為加密貨幣永續合約設計，支援 CCXT 旗下的多個交易所。其核心優勢在於**訊號驅動的自動化交易**，特別是針對 Telegram 頻道訊號的深度解析與執行。

---

## ✨ 核心特色

### 🤖 智能交易執行 (以 AdTrack 為例)
- **智慧區間進場**：自動判定市價是否在區間內，決定市價搶單或限價掛單。
- **4 階梯止盈系統**：進場後自動部署 25% / 25% / 25% / 25% 的分批平倉單。
- **動態移動止損 (Trailing SL)**：
    - 達成 **TP1** -> 止損自動移至進場本金價 (Break-even)。
    - 達成 **TP2** -> 止損自動移至 TP1 價格，以此類推。
- **自動精度處理**：自動對齊 Bybit 交易所的數量與價格精度規範。

### 🔌 架構設計
- **可插拔適配器**：標準化交易所介面，輕鬆切換不同 CEX 或適配自定義交易所。
- **多維度監控面板**：基於 `rich` 實作的異步 Dashboard，實時顯示連線狀態、訊號統計與執行紀錄。
- **靈活配置**：支援 **USDT 固定本金** 或 **固定幣種顆數** 兩種下單模式。
- **模擬環境友善**：原生支援 Bybit Testnet (Sandbox)，安全測試策略邏輯。

---

## 🛠 安裝與配置

### 1. 環境準備
```bash
# 建立虛擬環境
python -m venv .venv

# 啟動環境 (Windows)
.\.venv\Scripts\activate
# 啟動環境 (macOS/Linux)
source .venv/bin/activate

# 安裝依賴
pip install -r requirements.txt
```

### 2. 系統配置
1. 將 `config.yaml.example` 複製並重新命名為 `config.yaml`。
2. 填入您的交易所 API Key。
3. 若要監聽 Telegram，請填入 `api_id` 與 `api_hash`。
4. **Session 移植**：若已有 `.session` 檔案，請直接放入根目錄並在 YAML 中對齊 `session_name` 以跳過二次驗證。

---

## 🚀 快速啟動

執行主程式啟動互動式選單，依照提示選擇交易所與模式：
```bash
python main.py
```

---

## 📂 系統架構說明

- `src/core/`：定義核心介面 (`ABC`) 與策略引擎調度器。
- `src/adapters/`：交易所連接層，負擔 API 轉換工作。
- `src/infrastructure/`：
    - `signal_receivers/`：Telegram 監聽器。
    - `message_parsers/`：訊號格式解碼邏輯 (如 AdTrack Parser)。
- `src/strategies/`：交易策略邏輯實作。
- `src/ui/` & `src/cli/`：終端機視覺化與互動介面。

---

## 📜 免責聲明
本專案僅供技術研究與參考之用，不構成任何投資建議。量化交易存在高風險，使用本程式進行真實交易所產生的損益由使用者自行負責。

## 📜 授權
MIT License.
