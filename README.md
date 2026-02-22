# 喵喵選股 cat_system

台股客製化選股系統 — 機構級分析，散戶友善介面。

## 功能

- **多維度篩選** — 自訂漲幅、成交量、股價、技術指標條件組合
- **週轉率 Top200 分析** — 漲停股、五日新高/新低、突破糾結均線、成交量放大、法人連買
- **v1 選股引擎** — 公式解析器 + 跨越/跌破運算子 (CROSS_UP/CROSS_DOWN)
- **K 線圖表** — Lightweight Charts 即時 K 線 + 技術指標疊加
- **策略管理** — 4 大均線策略 (極度多頭/穩健多頭/支撐守穩/突破)
- **回測系統** — 歷史策略績效驗證
- **資料匯出** — Excel (XML Spreadsheet)、CSV、JSON

## 技術架構

| 層級 | 技術 |
|------|------|
| 後端 | Python 3.12 + FastAPI + SQLAlchemy (async) + SQLite |
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS |
| 狀態管理 | Zustand + TanStack Query |
| UI 元件 | shadcn/ui (Radix) + Recharts + Lightweight Charts |
| 資料源 | FinMind API + Yahoo Finance + TWSE Open Data + TWSE MIS (盤中即時) |

## 快速開始

### 後端
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 前端
```bash
cd frontend
npm install
npm run dev
```

開啟 http://localhost:5173 (前端) / http://localhost:8000/docs (API 文件)

## API 架構

### Legacy API (`/api/...`)
| 端點 | 說明 |
|------|------|
| `GET /api/stocks/filter` | 篩選股票 |
| `GET /api/stocks/{symbol}` | 股票詳情 + 技術指標 |
| `GET /api/turnover/top200-limit-up` | 週轉率前200漲停股 |
| `GET /api/turnover/ma-breakout` | 突破糾結均線 |
| `GET /api/turnover/volume-surge` | 成交量放大 |
| `GET /api/turnover/institutional-buy` | 法人連買 |
| `GET /api/stocks/realtime` | 盤中即時報價 (TWSE MIS) |
| `POST /api/backtest/run` | 執行回測 |

### v1 API (`/api/v1/...`)
| 端點 | 說明 |
|------|------|
| `GET /api/v1/tickers` | 股票清單 |
| `POST /api/v1/screen` | 自訂條件選股 |
| `GET /api/v1/chart/{ticker_id}` | K 線資料 |
| `GET /api/v1/strategies` | 策略列表 |
| `POST /api/v1/sync` | 手動資料同步 |

## 部署

### Zeabur (推薦)
Push 到 GitHub 後 Zeabur 自動偵測 `zeabur.toml`，使用根目錄 Dockerfile 部署。

### Docker
```bash
docker build -t cat-system .
docker run -p 8000:8000 cat-system
```

### Docker Compose (含 PostgreSQL + Redis)
```bash
docker-compose up -d
```

## 環境變數

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `FINMIND_API_TOKEN` | FinMind API Token (選填) | - |
| `DATABASE_URL` | 資料庫連線 | `sqlite+aiosqlite:///./twse_filter.db` |
| `CORS_ORIGINS` | 允許的來源 | `http://localhost:5173,http://localhost:3000` |

## 測試

```bash
cd backend
python -m pytest tests/ -v
```

## 授權

MIT License
