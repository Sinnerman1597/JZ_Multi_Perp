# 交易系統規格書 (可插拔式架構版)

## 1. 系統概述

本系統為一個**高度模組化**且**可插拔 (Pluggable)** 的加密貨幣交易框架。核心基於 Python 開發，旨在提供一個統一的介面層，將具體的交易邏輯與底層交易所實現解耦。

### 核心目標：
1.  **高度解耦**：策略與交易所完全分離，策略只依賴統一的介面。
2.  **多源支援**：同時支援 CCXT 全系列交易所、非 CCXT 支持的 CEX 以及基於 Web3 的 DEX。
3.  **模組復用**：各個組件（適配器、解析器、策略）均可獨立遷移至其他專案。
4.  **自動化與監控**：涵蓋從訊號獲取、智慧下單到實時風險監控的全流程。

---

## 2. 功能需求

### 2.1 交易所與適配器 (Adapters)
系統不直接綁定 CCXT，而是透過**適配器模式 (Adapter Pattern)** 實現擴展：
*   **CCXT 適配器**：整合 CCXT 支援的 100+ CEX。
*   **自定義 CEX 適配器**：針對 CCXT 未支援的小型交易所，可自行實作 API 調用。
*   **DEX 適配器**：使用 `Web3.py` 或特定鏈的 SDK 連接去中心化交易所（如 Uniswap, PancakeSwap）。
*   **功能涵蓋**：
    *   **公開數據**：市場行情、K 線、深度圖。
    *   **私有操作**：資產查詢、下單、撤單、槓桿設置。
*   **自動精度處理**：適配器內部自動處理不同交易所的下單精度與數量限制。

### 2.2 執行模式與策略模組化
系統支援兩種核心執行驅動模式，使用者可根據需求啟動其中之一或兩者並行：

1.  **自主策略模式 (Self-Managed)**：每個策略獨立為一個 Python 類別，繼承自基類 `StrategyBase`，基於 K 線或訂單簿數據自主產生訊號。
2.  **外部監測模式 (Signal-Driven)**：透過監聽外部訊號源（如 TG, TV）觸發交易。

*   **策略包含**：
    *   **初始化**：載入參數（如 MA 週期）。
    *   **觸發機制**：主動輪詢數據或等待外部訊號回調。

### 2.3 訊號與外部整合
*   **多源訊號**：支援 Telegram 頻道監控、Discord、TradingView Webhook。
*   **智慧解析**：
    *   **結構化解析**：直接處理 JSON 格式（如 TradingView 警報）。
    *   **非結構化解析**：透過規則匹配或 NLP 從文字訊息提取交易要素。

### 2.4 風險管理
*   **核心管控**：全局止損、單筆倉位上限、最大回撤限制。
*   **動態調整**：支援根據餘額自動計算下單量。

### 2.5 互動式控制介面 (Interactive CLI/TUI)
*   **啟動選單**：系統啟動時提供互動式選單，允許使用者動態選擇交易所（如 Binance, OKX）與欲執行的交易策略。
*   **上下文感知配置 (Context-aware Config)**：
    *   **動態參數流程**：CLI 會讀取策略模組的配置需求，自動過濾無關選項。
    *   **手動策略**：提示選擇幣對、槓桿、MA 週期等。
    *   **訊號策略 (TG/TV)**：自動隱藏幣對選擇，僅提示全局風控（如單筆下單上限、槓桿上限）與訊號源確認。
*   **即時監控面板**：執行期間透過終端機顯示 Dashboard，包含當前餘額、持倉狀態、最近成交紀錄與盈虧點數。
*   **指令互動**：支援在程式運行中輸入指令（如 `stop`, `pause`, `status`, `close_all`）。

---

## 3. 系統架構 (Clean Code & SOLID Design)

### 3.1 邏輯分層
1.  **Core Interface Layer**：定義所有交易所與策略必須遵守的「契約」（Abstract Base Classes）。
2.  **Adapter Layer**：具體的實作層，處理與不同交易所 API 的對接。
3.  **Engine Layer**：負責調度訊號、觸發策略並管理訂單生命週期。
4.  **CLI Controller Layer**：提供互動式終端介面，處理使用者輸入並調度引擎。使用 `questionary` 或 `prompt_toolkit` 實現。
5.  **Application Layer**：入口點與配置加載。

**架構圖：**
```text
[User Input] <--> [CLI Controller]
                        |
[Signal Source] -> [Signal Receiver] -> [Message Parser]
                                            |
                                    (Trade Instruction)
                                            |
[Strategy Engine] <-------------------------+
       |
       +--> [Strategy Module] (只看 Interface)
                   |
            (Order Request)
                   |
    [Exchange Interface (抽象層)]
                   |
    +--------------+--------------+
    |              |              |
[CCXT Adapter] [Custom Adapter] [DEX Adapter]
    |              |              |
 [Binance]      [Small CEX]    [Uniswap]
```

### 3.2 目錄結構建議
為了方便模組復用，建議目錄結構如下：
*   `src/core/`：存放介面定義（ABC），此資料夾最為獨立。
*   `src/adapters/`：存放各式交易所適配器。
*   `src/message_parsers/`：訊號解析邏輯。
*   `src/strategies/`：交易策略邏輯。
*   `src/cli/`：互動選單邏輯與 Dashboard 面板實作（如基於 `rich`）。
*   `src/infrastructure/`：日誌、資料庫、設定檔加載。

---

## 4. 擴展指南

### 4.1 如何新增一個交易所？
1.  在 `src/adapters/` 建立新檔案（例如 `my_exchange_adapter.py`）。
2.  繼承 `src/core/interfaces/exchange_abc.py`。
3.  實作 `create_order`、`get_balance` 等必要方法。
4.  在設定檔中將 `exchange_type` 指向此新類別即可。

---

## 5. 開發與部署

*   **開發原則**：遵循 **SOLID**、**DRY**、**KISS**、**YAGNI**、**Clean Code** 原則，特別是 **DIP (依賴反轉)**。
*   **環境**：Python 3.8+。
*   **安全性**：API 密鑰與私鑰嚴格透過環境變數管理。
*   **部署**：支援 Docker 化部署與 Prometheus 監控指標輸出。