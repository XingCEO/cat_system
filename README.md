# TWSE 漲幅區間篩選器 Web Edition

台股漲幅區間篩選系統 - 提供即時篩選、技術分析、回測等功能。

### 3. 高周轉率漲停股分析
- **核心邏輯**：
  1. 篩選當日周轉率前 20 名股票
  2. 從中找出漲幅達 9.9% 以上的強勢股
  3. 分析其封單量、開板次數、漲停類型
- **功能特色**：
  - 快速預設：超強游資股、妖股候選、大戶進場、低價飆股
  - 視覺化圖表：周轉率分布、散點圖、產業分布
  - 歷史回測：分析連續多日入榬的強勢股
- **API 端點**：
  - `GET /api/turnover/limit-up` - 取得前20名中的漲停股
  - `GET /api/turnover/top20` - 取得周轉率前20完整名單

### 4. 回測系統
- 設定回測條件（日期範圍、初始資金、手續費）
- 執行策略並計算績效（總報酬、年化報酬、勝率、最大回檔）
- 視覺化回測結果（淨值走勢圖）

## 功能特色

- 📊 **即時篩選** - 自訂漲幅、成交量、股價區間
- 📈 **技術分析** - RSI、MACD、KD、布林通道
- 🔄 **批次比對** - 多日重複出現股票篩選
- 📉 **回測分析** - 歷史策略績效驗證
- 👀 **監控清單** - 條件達成自動通知
- 📤 **資料匯出** - CSV、Excel、JSON

## 技術架構

**後端**: Python 3.10 + FastAPI + SQLAlchemy + SQLite  
**前端**: React 18 + TypeScript + Tailwind CSS + Recharts  
**資料源**: FinMind API + 台灣證交所 Open Data

## 快速開始

### 方式一：Docker Compose (推薦)

```bash
# 1. 複製環境設定
cp .env.example .env

# 2. 啟動服務
docker-compose up -d

# 3. 開啟瀏覽器
# 前端: http://localhost:5173
# API:  http://localhost:8000/docs
```

### 方式二：本地開發

**後端啟動**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**前端啟動**
```bash
cd frontend
npm install
npm run dev
```

## 環境變數

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `FINMIND_API_TOKEN` | FinMind API Token (選填) | - |
| `DATABASE_URL` | 資料庫連線 | `sqlite:///./twse_filter.db` |
| `CORS_ORIGINS` | 允許的來源 | `http://localhost:5173` |

## API 端點

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/stocks/filter` | 篩選股票 |
| GET | `/api/stocks/{symbol}` | 股票詳情 |
| GET | `/api/stocks/{symbol}/indicators` | 技術指標 |
| POST | `/api/stocks/batch-compare` | 批次比對 |
| POST | `/api/backtest/run` | 執行回測 |
| GET | `/api/watchlist` | 監控清單 |
| GET | `/api/export/csv` | 匯出 CSV |

完整 API 文件：`http://localhost:8000/docs`

## 專案結構

```
├── backend/
│   ├── main.py          # FastAPI 主程式
│   ├── models/          # 資料庫模型
│   ├── routers/         # API 路由
│   ├── services/        # 業務邏輯
│   └── utils/           # 工具函式
├── frontend/
│   ├── src/
│   │   ├── components/  # React 元件
│   │   ├── pages/       # 頁面
│   │   ├── services/    # API 呼叫
│   │   └── store/       # 狀態管理
│   └── package.json
├── docker-compose.yml
└── README.md
```

## 已知限制

1. **資料來源限制**：
   - 目前主要使用 TWSE Open Data，每日更新一次。
   - 盤中即時資料需依賴 FinMind API，免費版可能有 Rate Limit 限制。
   - 若遇 FinMind 連線失敗，系統將自動降級使用 TWSE 盤後資料。

2. **歷史回測**：
   - 由於資料量龐大，回測範圍建議在 1 年以內，以免查詢過久。
   - 部分早期股票因代號變更或下市，可能無法查詢完整歷史。

3. **瀏覽器相容性**：
   - 建議使用 Chrome, Edge, Firefox, Safari 最新版本。
   - 不支援 IE 11 及以下版本。

## 故障排除

### 1. 顯示「今日非交易日」但確實是交易日
- 請檢查 API 連線是否正常 (`http://localhost:8000/docs`)
- 確認系統時間是否正確
- 可能是證交所資料尚未更新（通常在下午 2:00 後更新）

### 2. 圖表顯示空白或被裁切
- 請嘗試重新整理頁面
- 若使用手機瀏覽，請嘗試橫屏模式
- 確認瀏覽器縮放比例是否為 100%

### 3. CSV 匯出亂碼
- 檔案預設為 UTF-8 編碼 (含 BOM)，Excel 應能自動識別
- 若仍有亂碼，請在 Excel 中使用「資料 -> 從文字/CSV」匯入功能

## 授權

MIT License
# Big-Cat-
