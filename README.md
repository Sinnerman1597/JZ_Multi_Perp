# JZ_Multi_Perp 🚀
> 一個基於 Python 的高度可插拔、模組化量化交易框架。

JZ_Multi_Perp 專為加密貨幣永續合約設計，支援 CCXT 旗下的多個交易所。其核心優勢在於**訊號驅動的自動化交易**，特別是針對 Telegram 頻道訊號的深度解析與執行。

---

## ✨ 核心特色

### 🤖 智能交易執行 (以 AdTrack 為例)
- **多交易所智能路由**：支援 Bybit, OKX, Binance, Gate。系統自動檢測各所幣種支援度與槓桿上限，挑選最優路徑執行。
- **混合型止損 (Hybrid SL) [🆕New]**：解決交易所 API 限制（如 Bybit 500 筆查詢限制）後導致的監控失效。即便 API 報錯查不到單，系統也會自動進行「現價與目標價比對」，確保利潤達成時止損必定移動。
- **全自動對診與領養 (Auto-Reconcile) [🆕New]**：**方案 B 實作**。每 5 分鐘自動掃描全交易所持倉。若發現手動進場或掛單，系統將根據「訊號帳本」自動領養持倉並部署監控，無需手動修改 JSON。
- **智能進場判定 (Smart Entry)**：自動感應現價。若價格在訊號區間內則「市價搶單」；若在區間外則自動切換為「限價掛單」並預設 TP/SL。
- **生存校驗與清理 (Liveness Check)**：實時監控持倉量。若偵測到倉位已手動平倉或觸發止損歸零，監控任務將自動卸載以防止資源浪費。
- **動態移動止損 (Trailing SL)**：
    - 達成 **TP1** -> 止損自動移至進場本金價 (Break-even)。
    - 達成 **TP2** -> 止損自動移至 TP1 價格，以此類推。

### 🔌 架構設計與視覺化
- **訊號帳本 (Signal Ledger)**：自動保存所有歷史 Telegram 訊號於 `signal_history.json`，供自動對診系統回溯使用。
- **配置與啟動分離**：優化啟動流程。在使用者配置參數階段嚴格靜默背景任務，確保選單 UI 清潔，僅在正式啟動引擎後才開啟監控日誌。
- **多維度實時監控**：
    - **Dashboard**：實時顯示連線狀態、頻道訊號統計與執行紀錄。
    - **持倉摘要**：顯示幣種、方向、入場價、**即時現價**以及**未實現盈虧 % (PnL)**。
- **自動精度對齊**：動態讀取交易所市場規則，自動修正數量與價格的小數點位數。

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
python main_terminal.py
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
- `data/`：存放 `active_trades.json` (持倉快照) 與 `signal_history.json` (訊號帳本)。

---

## 📜 免責聲明
本專案僅供技術研究與參考之用，不構成任何投資建議。量化交易存在高風險，使用本程式進行真實交易所產生的損益由使用者自行負責。

## 📜 授權
MIT License.
