<div align="center">

# 喵喵選股 MeowStock

**台股客製化選股系統 — 機構級分析，散戶友善介面**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)](https://typescriptlang.org)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.x-06B6D4?logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://docker.com)
[![CI](https://github.com/XingCEO/cat_system/actions/workflows/ci-build-publish.yml/badge.svg)](https://github.com/XingCEO/cat_system/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[![TWSE](https://img.shields.io/badge/TWSE-台灣證券交易所-c41230?style=flat-square)](https://www.twse.com.tw)
[![Yahoo Finance](https://img.shields.io/badge/Yahoo_Finance-Data-7B1FA2?style=flat-square&logo=yahoo&logoColor=white)](https://finance.yahoo.com)
[![FinMind](https://img.shields.io/badge/FinMind-API-FF6F00?style=flat-square)](https://finmind.github.io)

</div>

---

## 功能亮點

| 功能 | 說明 |
|:-----|:-----|
| **多維度選股** | 自訂漲幅、成交量、股價、技術指標條件組合，支援 AND / OR 邏輯 |
| **週轉率 Top200** | 漲停股、五日新高/新低、突破糾結均線、成交量放大、法人連買 |
| **K 線圖表** | Lightweight Charts 即時 K 線 + MA / RSI / MACD / KD / 布林通道 |
| **v1 選股引擎** | 公式解析器 + 跨越/跌破運算子 (`CROSS_UP` / `CROSS_DOWN`) |
| **策略管理** | 極度多頭 / 穩健多頭 / 支撐守穩 / 突破 四大均線策略 |
| **回測 & 匯出** | 歷史策略績效驗證 + Excel / CSV / JSON 一鍵匯出 |

---

## 技術架構

| 層級 | 技術 |
|:-----|:-----|
| **前端** | React 18 · TypeScript · Vite · Tailwind CSS |
| **狀態管理** | Zustand · TanStack Query |
| **UI 元件** | shadcn/ui (Radix) · Recharts · Lightweight Charts |
| **後端** | Python 3.12 · FastAPI · SQLAlchemy (async) · pandas · pandas-ta |
| **資料庫** | SQLite (開發) / PostgreSQL (生產) |
| **資料源** | FinMind API · Yahoo Finance · TWSE Open Data · TWSE MIS (盤中即時) |
| **部署** | Docker · GitHub Actions · Zeabur / Render |

---

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

> 前端: http://localhost:5173 | API 文件: http://localhost:8000/docs

### Docker

```bash
docker build -t cat-system .
docker run -p 8000:8000 cat-system
```

### Docker Compose (含 PostgreSQL + Redis)

```bash
docker-compose up -d
```

---

## API 架構

<details>
<summary><b>Legacy API</b> — <code>/api/...</code></summary>

| 端點 | 方法 | 說明 |
|:-----|:-----|:-----|
| `/api/health` | `GET` | 健康檢查 |
| `/api/status` | `GET` | 系統狀態 (版本、股票數) |
| `/api/stocks/filter` | `GET` | 篩選股票 |
| `/api/stocks/{symbol}` | `GET` | 股票詳情 + 技術指標 |
| `/api/stocks/industries` | `GET` | 產業列表 |
| `/api/turnover/top200-limit-up` | `GET` | 週轉率前200漲停股 |
| `/api/turnover/ma-breakout` | `GET` | 突破糾結均線 |
| `/api/turnover/volume-surge` | `GET` | 成交量放大 |
| `/api/turnover/institutional-buy` | `GET` | 法人連買 |
| `/api/backtest/run` | `POST` | 執行回測 |
| `/api/export/*` | `GET` | Excel 匯出 |

</details>

<details>
<summary><b>v1 API</b> — <code>/api/v1/...</code></summary>

| 端點 | 方法 | 說明 |
|:-----|:-----|:-----|
| `/api/v1/tickers` | `GET` | 股票清單 (支援 limit/offset) |
| `/api/v1/screen` | `POST` | 多維度自訂條件選股 |
| `/api/v1/chart/{ticker_id}/kline` | `GET` | K 線歷史資料 (daily/weekly/monthly) |
| `/api/v1/strategies` | `CRUD` | 策略管理 |
| `/api/v1/sync` | `POST` | 手動資料同步 (5 分鐘冷卻) |

</details>

---

## 環境變數

| 變數 | 說明 | 預設值 |
|:-----|:-----|:-------|
| `FINMIND_API_TOKEN` | FinMind API Token (選填) | — |
| `DATABASE_URL` | 資料庫連線 | `sqlite+aiosqlite:///./twse_filter.db` |
| `CORS_ORIGINS` | 允許的來源 | `http://localhost:5173,http://localhost:3000` |

---

## 測試

```bash
cd backend
python -m pytest tests/ -v   # 31 tests
```

---

## 授權

MIT License
