# Cat System

<div align="center">

<img src="https://img.shields.io/badge/Performance-Sub--Millisecond-00C853?style=for-the-badge" alt="Performance" />
<img src="https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=white" alt="React" />
<img src="https://img.shields.io/badge/FastAPI-Modern-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
<img src="https://img.shields.io/badge/TypeScript-Strict-3178C6?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript" />

### High-Performance Taiwan Stock Screening Platform

*Institutional-grade analytics. Retail-friendly interface.*

[Performance](#-ultra-low-latency-engine) · [Features](#-key-features) · [Quick Start](#-quick-start) · [Tech Stack](#-technology)

---

</div>

## Ultra-Low Latency Engine

Our proprietary **Multi-Tier Caching Architecture** delivers institutional-grade performance:

| Operation | Latency | Description |
|-----------|---------|-------------|
| Dashboard Switch | **< 1ms** | Instant stock switching with in-memory cache |
| Indicator Load | **< 100ms** | Pre-computed RSI, MA, MACD, KD, Bollinger |
| Historical Query | **< 300ms** | 2-year data with intelligent delta sync |

**Stale-While-Revalidate (SWR):** The UI displays cached data instantly while background processes fetch the latest updates. You never wait for data.

---

## Key Features

### Real-Time Market Intelligence

| Feature | Description |
|---------|-------------|
| **High-Turnover Tracking** | Monitor top 200 stocks by turnover rate with limit-up detection |
| **MA Strategy Scanner** | 4 proven moving average strategies with automatic signal detection |
| **Technical Indicators** | RSI(14), MACD(12,26,9), KD Stochastic, Bollinger Bands |
| **Professional Charts** | Interactive K-line with drawing tools and multi-timeframe analysis |

### Moving Average Strategies

| Strategy | Signal | Use Case |
|----------|--------|----------|
| **Extreme Bullish** | Price > MA5 with bullish alignment | Momentum trading |
| **Steady Bullish** | Price > MA20 with bullish alignment | Swing trading |
| **Support Hold** | Price > MA60 with bullish alignment | Position trading |
| **Breakout** | MA convergence < 1% with volume surge | Trend reversal |

### Turnover Analysis

- Track limit-up stocks in the top 200 turnover rankings
- Day 1/3/5/7 performance tracking for limit-up events
- Statistical analysis of continuation patterns

---

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.9+

### Step 1: Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Step 2: Frontend

```bash
cd frontend
npm install
npm run dev
```

### Access Points

| Service | URL |
|---------|-----|
| Web Application | http://localhost:5173 |
| API Documentation | http://localhost:8000/docs |
| Health Check | http://localhost:8000/api/health |

---

## Technology

| Layer | Stack |
|-------|-------|
| **Frontend** | React 18 + TypeScript + Vite |
| **UI Components** | shadcn/ui + Tailwind CSS |
| **Charts** | Lightweight Charts + Recharts |
| **State & Cache** | TanStack Query (SWR) + Zustand |
| **Backend** | FastAPI + Python |
| **Database** | SQLite with async I/O |

### Data Sources

| Source | Type | Latency |
|--------|------|---------|
| TWSE MIS API | Real-time quotes | 10-30s |
| FinMind API | Historical OHLCV | EOD |
| Yahoo Finance | Fallback source | 15min |

---

## API Highlights

```http
GET /api/stocks/{symbol}/kline          # K-line with all indicators
GET /api/turnover/top20                 # Top 20 turnover stocks
GET /api/turnover/ma-strategy/{type}    # MA strategy screening
POST /api/turnover/track                # Create tracking task
GET /api/turnover/track/stats           # Performance statistics
```

Full interactive documentation available at `/docs` after starting the backend.

---

## Security

- Input validation on all endpoints
- SQL injection protection via ORM
- CORS policy enforcement
- Path traversal prevention

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

<div align="center">

**Built for traders who demand speed.**

Taiwan Stock Exchange Data · Real-Time Analytics · Production Ready

</div>
