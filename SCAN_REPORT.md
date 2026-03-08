# 專案完整掃描報告 — 貓星人賺大錢 (cat_system)

日期：2026-03-08

## 一、專案概覽
- 全名：喵喵選股 / MeowStock
- 技術棧：Backend Python 3.12 + FastAPI + SQLAlchemy(async)；Frontend React 18 + TypeScript + Vite + Tailwind
- 核心功能：多維度選股篩選、技術指標 (MA/RSI/MACD/KD)、K 線圖、策略管理、回測、匯出
- 架構：Legacy API (`/api/...`) 與 v1 API (`/api/v1/...`) 並存；v1 為重構後的篩選引擎與 chart/strategy 模組

## 二、重要目錄與檔案（摘要）
- `backend/`
  - `main.py` — FastAPI 入口；Lifespan 處理、背景預熱、週期刷新與靜態前端路徑偵測
  - `config.py` — Pydantic 設定（環境、快取、DB URL 等）
  - `database.py` — 非同步 SQLAlchemy 引擎與 DB URL 解析（支援 sqlite 與 postgresql+asyncpg）
  - `app/engine/` — 篩選引擎（`screener.py`）、運算子（`operators.py`）、公式解析（`formula_parser.py`）、資料同步（`data_sync.py`）
  - `app/api/v1/` — v1 路由集合（`screen.py`, `chart.py`, `tickers.py`, `strategies.py` 等），含 `/api/v1/screen` 與 `/api/v1/chart/{ticker_id}/kline`
  - `services/` — `data_fetcher`（FinMind/TWSE/Yahoo）、`cache_manager`、`stock_filter`、`calculator`、`high_turnover_analyzer` 等
  - `models/` & `app/models/` — Legacy 與 v1 ORM 模型（共用 SQLAlchemy Base 注意不要混用）
  - `tests/` — pytest 測試（包含 `test_screener.py`, `test_data_sync.py` 等）

- `frontend/`
  - `src/` — React pages/components、`stores`（Zustand）、`services`（v1 API client）
  - `package.json`, `vite.config.ts` — 開發/建置設定與 `dev` proxy 到 `http://127.0.0.1:8000`

- 部署與 CI
  - `Dockerfile` — multi-stage，前端 build → 後端 uvicorn
  - `docker-compose.yml` — local compose 範例（postgres + redis 支援）
  - `render.yaml`, `zeabur.toml` — cloud deploy 設定

## 三、關鍵實作細節與注意點
- 篩選引擎
  - `screener.py` 流程：載入最新/多日資料 → 解析/執行自定公式 (`formula_parser.safe_eval_formula`) → 對每條 rule 生成 mask → AND/OR 合併
  - `operators.cross_up/cross_down` 使用 groupby(...).shift(1) 計算，不會 mutate 原始 DataFrame（設計上避免副作用）
  - 以 dict-based row -> `pd.DataFrame([dict(r._mapping) ...])` 建構 DataFrame（避免 positional mismatch）

- 公式解析器（`formula_parser.py`）
  - 使用 token 白名單/正則與有限運算子集合，並透過 `pandas.eval()` 執行，限制長度與 token 數量以防 DOS
  - 小心允許的 tokens 與 operators，避免引入可執行程式碼或屬性存取（已移除 `.` token）

- 資料同步（`data_sync.py`）
  - 支援從 Legacy `services.data_fetcher` 抓取並同步到 v1 表（Ticker、DailyPrice、DailyChip）
  - 同步使用 API 回傳的實際日期（避免日期偏差）及批次查詢以避免 N+1
  - 手動 / 背景 sync 有 5 分鐘 cooldown（`_SYNC_COOLDOWN = 300`）
  - `_backfill_indicators` 有 fallback 到 legacy data fetcher，batch limit 調整到 200

- Data Fetcher
  - `services/data_fetcher.py` 整合 FinMind / TWSE / Yahoo，具重試、共享 httpx client 與 cache_manager 使用

- Database
  - `database.py` 會自動轉換 `postgres://` → `postgresql+asyncpg://`，並支援從環境變數 (POSTGRES_URI / POSTGRES_HOST 等) 組合連線字串

## 四、測試與品質
- 測試覆蓋重點：screener helper、data_sync helper、operators 等核心邏輯（pytest）
- 建議：在本地執行 `python -m pytest tests/ -q` 確認目前狀態；CI workflow（若存在）亦應跑 coverage

## 五、潛在風險與改進建議
- 公式解析安全性：確保 `ALLOWED_FIELDS` 與 `ALLOWED_OPERATORS` 維護妥善並定期審查，避免未預期 token 被允許
- 大量資料處理效能：若資料量成長，`load_latest_data` 與 merge 操作可能成為瓶頸，建議檢查 DB 索引、分頁或分批處理
- 同步可靠性：外部 API (FinMind) 不穩需有觀察與退避策略（現有 retry 與 fallback 已部分處理）
- 測試覆蓋：建議新增 integration tests 測試 v1 API 路徑（/api/v1/screen）與主要 SQL 操作

## 六、快速操作指令
在 workspace 根目錄執行以下指令：

```bash
# 啟用虛擬環境（Windows PowerShell 範例）
& ".venv\Scripts\Activate.ps1"
cd backend
python -m pytest tests/ -q
```

## 七、下一步建議（你可以選）
- 我可以：
  1. 在本地執行測試並回報失敗項目與錯誤日誌
  2. 深入審查 `formula_parser.py` 的 token/白名單實作與邊界
  3. 審查 `app/models` 的 ORM 欄位與索引以優化查詢

---
報告檔案建立於專案根目錄：`SCAN_REPORT.md`。若要我執行上述任一下一步，請回覆編號。