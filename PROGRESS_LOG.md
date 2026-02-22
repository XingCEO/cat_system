# 專案進度記錄

## 最後更新時間
2026-02-22

---

## 已完成功能

### 1. 突破糾結均線篩選 (MA Breakout)
**檔案位置:** `backend/services/high_turnover_analyzer.py` (第973-1122行)

**三個篩選條件 (全部已實作並驗證):**
1. **今日開盤價 >= 昨日收盤價** - 跳空或平開
2. **當日收盤價 >= 五日前收盤價** - 短線走強
3. **當日最低價 >= 五日前最低價** - 支撐墊高

**額外條件:**
- 均線糾結: MA5/MA10/MA20 在 3% 範圍內
- 突破條件: 今日收盤價 > max(MA5, MA10, MA20)

**返回欄位:**7 
- `today_open` - 今日開盤價
- `yesterday_close` - 昨日收盤價
- `today_low` - 今日最低價
- `five_days_ago_close` - 五日前收盤價
- `five_days_ago_low` - 五日前最低價
- `gap_up` - 跳空幅度(%)
- `ma5`, `ma10`, `ma20` - 均線值
- `ma_range` - 均線糾結範圍(%)

---

### 2. 週轉率前200名篩選器
**前端檔案:** `frontend/src/pages/TurnoverFiltersPage.tsx`
**後端檔案:** `backend/routers/turnover.py`, `backend/services/high_turnover_analyzer.py`

**已完成的篩選類型:**
| 篩選類型 | API 端點 | 狀態 |
|---------|---------|------|
| 漲停股 | `/api/turnover/top200-limit-up` | ✅ 完成 |
| 漲幅區間 | `/api/turnover/top200-change-range` | ✅ 完成 |
| 五日創新高 | `/api/turnover/top200-5day-high` | ✅ 完成 |
| 五日創新低 | `/api/turnover/top200-5day-low` | ✅ 完成 |
| 突破糾結均線 | `/api/turnover/ma-breakout` | ✅ 完成 |
| 成交量放大 | `/api/turnover/volume-surge` | ✅ 後端完成，前端已加入 |
| 法人連買 | `/api/turnover/institutional-buy` | ✅ 後端完成，前端已加入 |

---

### 3. 技術修復

#### Yahoo Finance 整合
- 使用 Yahoo Finance API 取代 FinMind (FinMind 對 2025/2026 日期返回 400 錯誤)
- 加入 429 Rate Limit 重試機制 (2, 4, 6 秒指數退避)
- 限制查詢範圍為週轉率前200名以減少 API 請求

#### 快取機制
- MA Breakout 已禁用快取，每次查詢都重新計算
- 其他篩選仍使用快取以提升效能

---

## 全部功能已完成 ✅

### 驗證結果 (2026-01-31)

| 項目 | 狀態 | 說明 |
|------|------|------|
| TypeScript 編譯 | ✅ 通過 | `npm run build` 成功，無錯誤 |
| 成交量放大篩選 | ✅ 完成 | 前端 UI + API + 後端服務全部就緒 |
| 法人連買篩選 | ✅ 完成 | 前端 UI + API + 後端服務全部就緒 |
| 複合篩選 | ✅ 完成 | 支援多條件組合篩選 |

### 成交量放大篩選
- 前端: `TurnoverFiltersPage.tsx` 第 444-458 行
- API: `api.ts` 第 247-254 行 `getVolumeSurge()`
- 後端: `turnover.py` 第 403-422 行 `/volume-surge`
- 服務: `high_turnover_analyzer.py` 第 1346 行 `get_volume_surge()`

### 法人連買篩選
- 前端: `TurnoverFiltersPage.tsx` 第 460-474 行
- API: `api.ts` 第 257-264 行 `getInstitutionalBuy()`
- 後端: `turnover.py` 第 425-444 行 `/institutional-buy`
- 服務: `high_turnover_analyzer.py` 第 1422 行 `get_institutional_buy()`

---

## 重要檔案路徑

```
cat_system/
├── Dockerfile                                 # 統一部署 (multi-stage)
├── zeabur.toml                                # Zeabur 部署設定
├── docker-compose.yml                         # 本地全套 (PG+Redis)
├── render.yaml                                # Render 部署設定
├── backend/
│   ├── main.py                                # FastAPI 入口 (serves SPA)
│   ├── config.py                              # Pydantic 設定 (v2.0.0)
│   ├── database.py                            # Async SQLAlchemy
│   ├── routers/turnover.py                    # 週轉率 API 路由
│   ├── services/high_turnover_analyzer.py     # 核心分析邏輯
│   ├── services/data_fetcher.py               # 資料獲取
│   ├── app/engine/                            # v1 選股引擎
│   ├── app/api/v1/                            # v1 API 路由
│   └── tests/                                 # 單元測試 (31 tests)
├── frontend/
│   ├── src/pages/                             # React 頁面
│   ├── src/stores/store.ts                    # Zustand 狀態管理
│   └── src/services/api.ts                    # API 呼叫
└── PROGRESS_LOG.md                            # 本進度記錄
```

---

## 啟動指令

```bash
# 後端 (Port 8000)
cd "/Users/xuser/Documents/貓星人賺大錢 2/backend"
PYTHONDONTWRITEBYTECODE=1 python3 -m uvicorn main:app --host 0.0.0.0 --port 8000

# 前端 (Port 5173)
cd "/Users/xuser/Documents/貓星人賺大錢 2/frontend"
npm run dev

# 清除快取
curl http://localhost:8000/api/cache/clear
```

---

## 測試驗證

### 突破糾結均線測試結果 (2026-01-30)
```
突破股數: 6

1. 3028 增你強
   條件1: 今日開盤(42.35) >= 昨日收盤(41.85) ✓
   條件2: 收盤價(46.0) >= 五日前收盤(40.7) ✓
   條件3: 今日最低(42.05) >= 五日前最低(40.6) ✓

2. 4956 光鋐
   條件1: 今日開盤(21.75) >= 昨日收盤(21.65) ✓
   條件2: 收盤價(23.3) >= 五日前收盤(20.85) ✓
   條件3: 今日最低(21.65) >= 五日前最低(20.5) ✓

3. 8112 至上
   條件1: 今日開盤(80.7) >= 昨日收盤(80.5) ✓
   條件2: 收盤價(84.6) >= 五日前收盤(78.4) ✓
   條件3: 今日最低(78.5) >= 五日前最低(75.2) ✓
```

---

## 注意事項

1. **快取問題:** 修改後端程式碼後需要:
   - 刪除 `__pycache__` 目錄
   - 重啟後端服務
   - 呼叫 `/api/cache/clear` 清除快取

2. **FinMind API:** 對 2025/2026 年份的日期會返回 400 錯誤，已改用 Yahoo Finance

3. **Yahoo Finance Rate Limit:** 已加入重試機制，但大量查詢時仍可能遇到 429 錯誤

---

## v2.0 全面檢修 (2026-02-22)

### Bug 修復 (9 項)
| 項目 | 修復內容 |
|------|---------|
| cross_up/cross_down | 不再汙染原始 DataFrame，改用局部變數 |
| DataFrame 建構 | 3 處改為 dict-based，避免欄位錯位 |
| end_date 參數 | volume-surge / institutional-buy 端點正確轉發 |
| track 端點 | 從 TODO stub 改為實際呼叫 create_track / get_track_stats |
| config 版本 | config.py 1.0.0 → 2.0.0，與 main.py 一致 |
| store 目錄 | `store/` → `stores/`，5 個前端檔案 import 修正 |
| Excel 匯出 | CSV 偽裝改為真正 XML Spreadsheet 格式 |
| v1 資料管道 | 新增 data_sync.py (sync_tickers / sync_daily_prices) |
| 啟動同步 | main.py lifespan 自動同步 v1 股票基本資料 |

### 單元測試 (31 tests, 0.82s)
- `test_operators.py` — 7 tests (cross 運算子不汙染、布林回傳)
- `test_screener.py` — 11 tests (安全轉換、apply_rule 各運算子)
- `test_data_sync.py` — 8 tests (safe_float/int 逗號、fallback、None)
- `test_config_and_endpoints.py` — 5 tests (版本一致、end_date 簽名、track 方法)

### 部署修復
| 項目 | 修復內容 |
|------|---------|
| 根目錄 Dockerfile | multi-stage build (frontend → backend/static → uvicorn) |
| zeabur.toml | 新增，指定 Dockerfile 部署 + port 8000 |
| .dockerignore | 新增，排除 node_modules/venv/.db |
| backend Dockerfile | Python 3.10 → 3.12 |
| render.yaml | 改用 Docker 部署 |
| requirements.txt | asyncpg 保留 (Zeabur 用 PostgreSQL) |

### Repo 遷移
- origin 從 `Cat-GoGo.git` 切換至 `cat_system.git`
- 所有後續開發推送至 `https://github.com/XingCEO/cat_system`
