# 🐱 Cat System

<div align="center">

<img src="https://img.shields.io/badge/React-18.3-61DAFB?style=for-the-badge&logo=react&logoColor=white" alt="React" />
<img src="https://img.shields.io/badge/TypeScript-5.6-3178C6?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript" />
<img src="https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
<img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />

**企業級台股智慧篩選系統**

*Professional Taiwan Stock Screening Platform*

[功能特色](#-功能特色) • [快速開始](#-快速開始) • [技術架構](#-技術架構) • [API 文件](#-api-文件)

---

</div>

## 🎯 專案簡介

Cat System 是一款專為台灣股市設計的專業級股票篩選與分析平台。透過先進的技術分析演算法與即時數據整合，提供投資者精準的市場洞察與決策輔助工具。

### 核心價值

- **🚀 即時監控** — 盤中即時報價，延遲僅 10-30 秒
- **📊 智慧篩選** — 多維度技術指標交叉篩選
- **📈 K線分析** — 專業級互動式 K 線圖表
- **🎯 均線策略** — 4 大均線策略自動識別

---

## ✨ 功能特色

### 盤中即時監控
實時追蹤週轉率前 50 名股票的即時報價，支援多資料源自動切換，確保數據穩定可靠。

### 均線策略篩選
四大核心策略自動識別：
| 策略 | 描述 | 適用情境 |
|------|------|----------|
| 🔴 極強勢多頭 | 多頭排列 + 價格站上 MA5 | 極速攻擊階段 |
| 🟠 穩健多頭 | 多頭排列 + 價格站上 MA20 | 中線偏多 |
| 🔵 波段支撐 | 多頭排列 + 價格站上 MA60 | 長線趨勢保護 |
| 🟣 均線糾結突破 | 均線間距 < 1% + 放量突破 | 新趨勢起點 |

### 專業 K 線圖表
- 支援日 K / 週 K / 月 K 週期切換
- MA5、MA10、MA20、MA60、MA120 均線顯示
- MACD、KD、RSI 技術指標
- 布林通道視覺化
- 點擊鎖定與拖曳縮放

### 週轉率分析
深度分析週轉率前 200 名股票，識別主力進場訊號與異常成交量。

---

## 🚀 快速開始

### 環境需求

- **Node.js** 18.0+
- **Python** 3.11+
- **npm** 或 **pnpm**

### 安裝步驟

```bash
# 1. 克隆專案
git clone https://github.com/XingCEO/cat_system.git
cd cat_system

# 2. 啟動後端服務
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 3. 啟動前端開發伺服器 (新終端)
cd frontend
npm install
npm run dev
```

### 存取服務

| 服務 | 網址 |
|------|------|
| 🌐 前端應用 | http://localhost:5173 |
| 🔧 API 文件 | http://localhost:8000/docs |
| ❤️ 健康檢查 | http://localhost:8000/api/health |

---

## 🏗 技術架構

```
cat_system/
├── backend/               # FastAPI 後端服務
│   ├── routers/          # API 路由模組
│   ├── services/         # 業務邏輯層
│   │   ├── realtime_quotes.py     # 即時報價服務
│   │   ├── enhanced_kline_service.py  # K線數據服務
│   │   └── analyzers/    # 技術分析模組
│   └── main.py           # 應用入口
│
├── frontend/              # React 前端應用
│   ├── src/
│   │   ├── pages/        # 頁面元件
│   │   ├── components/   # 可複用元件
│   │   │   ├── charts/  # 圖表元件
│   │   │   └── ui/      # UI 基礎元件
│   │   ├── services/     # API 服務層
│   │   └── store/        # 狀態管理
│   └── vite.config.ts    # Vite 配置
│
└── docker-compose.yml     # Docker 編排配置
```

### 技術棧

| 層級 | 技術選型 |
|------|----------|
| **前端框架** | React 18 + TypeScript |
| **UI 元件** | shadcn/ui + Tailwind CSS |
| **圖表引擎** | Lightweight Charts + Recharts |
| **狀態管理** | Zustand + TanStack Query |
| **後端框架** | FastAPI + Pydantic |
| **非同步處理** | aiohttp + asyncio |
| **數據快取** | cachetools TTL Cache |

### 數據來源

| 來源 | 用途 | 延遲 |
|------|------|------|
| 證交所 MIS API | 盤中即時報價 | 10-30s |
| TWSE OpenAPI | 每日交易數據 | EOD |
| FinMind API | 歷史 K 線數據 | EOD |
| Yahoo Finance | 備援數據源 | 15min |

---

## 📡 API 文件

### 核心端點

```http
# 股票篩選
GET /api/stocks/filter?change_min=5&change_max=10

# K 線數據
GET /api/stock/{symbol}/kline?period=daily&limit=250

# 即時報價
GET /realtime/top-turnover?limit=50

# 均線策略
GET /api/turnover/ma-strategy/{strategy}
```

### 完整文件

啟動後端服務後，訪問 [http://localhost:8000/docs](http://localhost:8000/docs) 查看 Swagger UI 互動式文件。

---

## 🔒 安全性

本系統已通過完整安全審計：

- ✅ 路徑穿越防護
- ✅ CORS 策略優化  
- ✅ 輸入驗證完善
- ✅ SQL 注入防護
- ✅ XSS 防護

詳見 [安全審計報告](#系統安全報告)。

---

## 📄 授權條款

本專案採用 [MIT License](LICENSE) 授權。

---

## 🌟 致謝

感謝所有開源社群的貢獻者，以及台灣證券交易所提供的公開資料 API。

<div align="center">

**Made with ❤️ in Taiwan**

Copyright © 2026 Cat System. All rights reserved.

</div>
