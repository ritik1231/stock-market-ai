# Frontend Redesign & India Power-Up Plan

## Current State Analysis

The system is a well-built multi-agent AI trading assistant targeting NSE/BSE. The backend is production-grade: LangGraph orchestration, pgvector RAG, Celery workers, structlog observability. The frontend is functional but minimal — 4 flat tabs, desktop-only, no market overview, and the News page shows nothing because news is only ingested during analysis runs (no standalone ingestion path).

---

## Why News Shows Nothing (Root Cause + Fix)

**Root cause:** `GET /api/news` correctly queries the `news_articles` table, but rows only exist there when the Research Agent runs (triggered by stock analysis). There is no standalone news ingestion endpoint or Celery beat schedule for news. If no analysis has been run, the table is empty.

**Backend fix (Task 0.1):** Add `POST /api/news/refresh` that calls `ingest_news` for all active watchlist tickers.

**Frontend fix (Task 0.2):** Add a "Fetch Latest News" button on the News page that calls this endpoint and invalidates the query cache.

---

## Making This Superpowerful for Indian Users

### What the market needs that this system can deliver:

| Feature | Why Indian Users Care | Backend Work Needed |
|---|---|---|
| Nifty 50 / Sensex live widget | Every Indian trader checks index first | yfinance has `^NSEI`, `^BSESN` |
| Market open/closed status | IST-aware (9:15–3:30 PM weekdays) | `market_calendar.py` exists |
| FII/DII tracker with chart | Institutional money moves markets; retail watches this daily | `fii_dii.py` exists, needs UI |
| Earnings calendar | Q1–Q4 result dates drive big moves | Fetch from NSE API |
| NSE circuit breaker alerts | Stocks that hit upper/lower circuit — huge in India | Already computed in quant agent |
| Indian news sources (ET, Mint, BS) | Relevant Indian financial news | `INDIAN_NEWS_FEEDS` already in `news_fetcher.py` |
| STCG/LTCG tax summary | Indian tax law: 15% STCG / 10% LTCG | `tax_calculator.py` exists |
| Nifty sector heatmap | Visual sector rotation — very popular | Group watchlist by sector |
| Bulk watchlist analysis | Analyze all tickers with one click | Existing `daily_watchlist_analysis` task |
| Portfolio XIRR calculator | Standard Indian investor metric | Client-side computation |
| SIP back-test | Extremely popular feature in India | Client-side with yfinance price history |
| Alert system (price/signal) | Get notified when AI flips signal | Redis pub/sub + WebSocket |

---

## Tech Stack Additions Needed

```
Current:         Vite + React 18 + TS + Tailwind + TanStack Query + Recharts + axios
To Add:
  - lightweight-charts (TradingView's OSS library) — candlestick charts
  - react-router-dom v6 — proper routing (remove tab state)
  - date-fns — date formatting with IST timezone support
  - react-hot-toast — replace custom Toast with proper toasts
  - framer-motion — subtle animations (optional, adds ~30kb)
  - clsx — cleaner conditional class merging
```

---

## Task List: Frontend Redesign

Tasks are ordered. Complete them in sequence. Each task is self-contained and shippable.

---

### TASK 0 — Fix News Page (Critical Bug)

#### 0.1 — Backend: Add news refresh endpoint

**File:** `app/api/routes/news.py`

Add below the existing GET route:

```python
from app.db import AsyncSessionLocal
from app.models.market import StocksWatchlist
from app.tools.news_fetcher import ingest_news
from sqlalchemy import select

@router.post("/news/refresh")
async def refresh_news(db: AsyncSession = Depends(get_db)):
    """Fetch and ingest latest news for all active watchlist tickers."""
    result = await db.execute(
        select(StocksWatchlist.ticker).where(StocksWatchlist.is_active.is_(True))
    )
    tickers = result.scalars().all()

    total = 0
    for ticker in tickers:
        count = await ingest_news(ticker, db)
        total += count

    return {"ingested": total, "tickers": tickers}
```

Also add a Celery beat schedule in `app/celery_app.py` to run news ingestion every 30 minutes during market hours.

#### 0.2 — Frontend: Add "Fetch News" button to NewsPage

**File:** `frontend/src/components/NewsPage.tsx`

Add a `useMutation` that calls `POST /api/news/refresh`. Show the button next to the page title. On success invalidate the `['news']` query. Display a count of articles ingested.

**API client addition (`frontend/src/api/client.ts`):**
```typescript
export const refreshNews = () =>
  api.post<{ ingested: number; tickers: string[] }>('/news/refresh').then(r => r.data)
```

---

### TASK 1 — Project Structure Refactor

**Goal:** Replace the 4-tab flat structure with a proper sidebar navigation that scales to 8+ sections.

#### 1.1 — Install dependencies

```bash
cd frontend
npm install react-router-dom date-fns clsx react-hot-toast lightweight-charts
```

#### 1.2 — Set up React Router

**File:** `frontend/src/main.tsx`

Wrap `<App />` with `<BrowserRouter>`.

**File:** `frontend/vite.config.ts`

Add `server.proxy` for `/api` → `http://localhost:8000` if not already present.

#### 1.3 — Create layout components

Create `frontend/src/components/layout/Sidebar.tsx`:
- Logo + "NSE/BSE Paper Mode" chip
- Nav items with icons (SVG or lucide-react):
  - Dashboard (home icon)
  - Watchlist (eye icon)
  - Analysis (brain icon)
  - Portfolio (briefcase icon)
  - Trades (arrow-up-down icon)
  - News (newspaper icon)
  - FII/DII (building icon)
  - Tax (calculator icon)
  - Settings (gear icon)
- On mobile: hidden, replaced by bottom tab bar

Create `frontend/src/components/layout/TopBar.tsx`:
- Market status badge (OPEN / CLOSED / PRE-MARKET in green/red/amber)
- Nifty 50 mini price ticker
- Sensex mini price ticker
- Time in IST (live clock)
- Theme toggle (dark is default)

Create `frontend/src/components/layout/BottomNav.tsx` (mobile only):
- 5 most-used tabs: Dashboard, Watchlist, Portfolio, News, Trades
- Active tab highlighted with indigo
- `md:hidden` class to hide on desktop

#### 1.4 — Update App.tsx

Replace tab state with `<Routes>` and `<Route>` for each page. Render `<Sidebar />` + `<TopBar />` + `<Outlet />` pattern.

```
Layout:
┌────────────────────────────────────────┐
│  TopBar (market status + index prices) │
├───────────────┬────────────────────────┤
│   Sidebar     │   Page Content         │
│   (desktop)   │                        │
│               │                        │
└───────────────┴────────────────────────┘
│       BottomNav (mobile only)          │
└────────────────────────────────────────┘
```

---

### TASK 2 — Dashboard Page (new)

**File:** `frontend/src/pages/DashboardPage.tsx`

This is the landing page. Shows a snapshot of everything.

#### 2.1 — Market Overview Strip

Horizontal scrollable row with live prices for:
- Nifty 50 (`^NSEI`)
- Sensex (`^BSESN`)
- Bank Nifty (`^NSEBANK`)
- Nifty IT (`^CNXIT`)
- USD/INR (`USDINR=X`)

Each chip shows: Name · Price · Change% with green/red color.

**Backend needed:** `GET /api/market/indices` → calls `yfinance.download` for these 5 tickers. Cache in Redis for 60 seconds.

**File to create:** `app/api/routes/market_overview.py`

#### 2.2 — Signal Summary Cards

3 stat cards in a row:
- Total watchlist tickers
- Tickers with BUY signal (count, green)
- Tickers with SELL signal (count, red)

#### 2.3 — Recent Agent Runs

Last 5 analysis runs with status badge. Link to full run detail.

#### 2.4 — Top News Headlines

3 most recent news articles with sentiment badge. Link to full News page.

#### 2.5 — Market Status Banner

During market hours: green "NSE OPEN — Market closes at 3:30 PM IST"
After hours: amber "NSE CLOSED — Opens Monday 9:15 AM IST"
On weekends: slate "Weekend — Market resumes Monday"

Logic uses IST timezone (UTC+5:30) and the existing `market_calendar.py`.

---

### TASK 3 — Watchlist Page Redesign

**File:** `frontend/src/pages/WatchlistPage.tsx` (rename from `WatchlistPanel.tsx`)

#### 3.1 — Grid layout improvements

- Change from 3-column max to responsive: `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4`
- Cards: minimum 280px wide
- Add a "Sort by" dropdown: Signal · Confidence · Price · Last Updated

#### 3.2 — Bulk analyze button

"Analyze All" button → calls `analyzeStock` for each ticker sequentially with 500ms delay between calls. Shows a progress bar: "Analyzing 3/12 tickers…"

#### 3.3 — Signal filter chips

Filter row above grid:
- All · BUY · SELL · HOLD · No Signal
- Active filter highlighted in indigo

#### 3.4 — Stock card improvements

- Add change % from previous close (fetch from price_snapshots or yfinance)
- Show mini sparkline (5-day price) using a tiny Recharts `<LineChart>`
- Circuit breaker alert icon (⚡) when near circuit limit
- "View Chart" link that opens a full-screen candlestick chart drawer

---

### TASK 4 — Candlestick Chart Drawer

**File:** `frontend/src/components/charts/CandlestickChart.tsx`

Uses `lightweight-charts` (TradingView's open-source charting library).

#### 4.1 — Backend: Price history endpoint

`GET /api/price/{ticker}/history?interval=1d&period=6mo`

Returns OHLCV array from `price_snapshots` table (or fallback to yfinance).

Response:
```json
[{ "time": "2026-01-02", "open": 234.5, "high": 240.0, "low": 230.1, "close": 238.9, "volume": 1234567 }]
```

#### 4.2 — Frontend chart component

Full-screen right-side drawer (slides in from right on desktop, bottom sheet on mobile).

Contains:
- Candlestick price chart (top 70% of chart area)
- Volume histogram (bottom 30%)
- Period selector: 1W · 1M · 3M · 6M · 1Y
- Overlay toggles: SMA 20 · SMA 50 · EMA 20 · Bollinger Bands
- Current signal badge in top-right corner of chart
- RSI panel below chart (collapsible)

#### 4.3 — Indicator overlays

Fetch `GET /api/signal/{ticker}` and overlay the indicator values:
- SMA 20 line (blue)
- SMA 50 line (orange)
- Bollinger Bands (shaded area)
- Entry/Stop/Target price lines (horizontal dashed lines) when a signal exists

---

### TASK 5 — News Page Redesign

**File:** `frontend/src/pages/NewsPage.tsx`

#### 5.1 — Layout: 2-panel design (desktop)

```
┌──────────────────────────────────────────────┐
│  [Fetch Latest News ▼]  [Filter: All Tickers]│
├──────────────────┬───────────────────────────┤
│  News Feed       │  Selected Article          │
│  (scrollable     │  - Full headline           │
│   list of cards) │  - AI sentiment analysis   │
│                  │  - Source + date           │
│                  │  - Impact on ticker        │
│                  │  - [Open Source ↗]         │
└──────────────────┴───────────────────────────┘
```

On mobile: single column, cards open a modal.

#### 5.2 — Sentiment aggregate chart

Bar chart at top showing sentiment distribution for the selected ticker over the past 7 days. Uses Recharts `<BarChart>`.

#### 5.3 — Ticker pill filter

Horizontal scrollable row of ticker pills (extracted from news articles). Click a ticker to filter. Active ticker pill highlighted.

#### 5.4 — Auto-refresh indicator

"Last updated 2 minutes ago" text that counts up. Pulsing green dot when news is being fetched.

#### 5.5 — Indian news source badges

Map source names to icons:
- Economic Times → "ET" badge (orange)
- Business Standard → "BS" badge (blue)
- Mint → "MINT" badge (teal)
- NewsAPI → "NA" badge (slate)
- Yahoo Finance → "YF" badge (purple)

---

### TASK 6 — Portfolio Page Redesign

**File:** `frontend/src/pages/PortfolioPage.tsx`

#### 6.1 — Summary bar redesign

Replace 4 equal metric cards with a priority layout:
- Large left card: Portfolio Value (big number + daily P&L)
- 3 smaller right cards: Equity · Cash · Buying Power

#### 6.2 — Equity curve improvements

- Add day/week/month/all toggle
- Show P&L annotation on hover (not just value)
- Color-fill: green fill if above starting value, red fill if below
- Show Nifty 50 as overlay line for comparison ("Beat the market" view)

#### 6.3 — Positions table improvements

- Add "Sector" column (from `stocks_watchlist.sector`)
- Colorize P&L % column (green/red gradient intensity)
- Sort by column click
- "Close Position" button (calls `POST /api/trade` with SELL action)

#### 6.4 — Sector allocation pie chart

Group positions by sector. Show a donut chart (Recharts `<PieChart>`) with % allocation per sector.

#### 6.5 — XIRR display

For each position, show the annualized return using:
- `buy_date` from `trades` table
- current `unrealized_pnl`

Formula (client-side):
```typescript
function xirr(investment: number, currentValue: number, daysHeld: number): number {
  return (Math.pow(currentValue / investment, 365 / daysHeld) - 1) * 100
}
```

---

### TASK 7 — FII/DII Tracker Page (new)

**File:** `frontend/src/pages/FiiDiiPage.tsx`

#### 7.1 — Backend: FII/DII data endpoint

`GET /api/fii-dii?days=30`

The existing `app/tools/fii_dii.py` fetches data. Add a route that calls it and caches for 4 hours.

Response:
```json
[{ "date": "2026-06-20", "fii_net": 1234.5, "dii_net": -456.7, "nifty_close": 24500 }]
```

#### 7.2 — Dashboard cards

- Today's FII net buy/sell (large number, green/red)
- Today's DII net buy/sell
- 30-day FII cumulative
- Market interpretation: "FIIs are NET BUYERS for 5 consecutive sessions — historically bullish"

#### 7.3 — FII vs DII vs Nifty chart

Dual-axis chart:
- Left Y-axis: FII/DII net flows (bar chart, FII = blue, DII = orange)
- Right Y-axis: Nifty 50 close (line chart, white)
- X-axis: dates (last 30 days)

#### 7.4 — Signal correlation

Text block: "On days when FII buys > ₹2000 Cr, Nifty closes green 73% of the time (based on last 90 days of data)."

---

### TASK 8 — Tax Calculator Page

**File:** `frontend/src/pages/TaxPage.tsx`

The backend `app/tools/tax_calculator.py` exists. The route `app/api/routes/tax.py` exists. This task is frontend-only.

#### 8.1 — Tax summary cards

Fetch `GET /api/tax/summary` for current financial year.

Display:
- STCG (Short Term Capital Gains) — held < 1 year, 15% tax rate
- LTCG (Long Term Capital Gains) — held > 1 year, 10% tax rate (above ₹1 lakh)
- Estimated tax liability
- Tax already "saved" by losses (harvesting opportunities)

#### 8.2 — Trade-by-trade breakdown

Table showing each closed trade with:
- Ticker · Buy Date · Sell Date · Days Held
- Buy Price · Sell Price · P&L
- Gain Type (STCG / LTCG)
- Estimated Tax

#### 8.3 — Tax harvesting suggestions

List open positions with losses. Show: "Selling WIPRO.NS now would harvest ₹4,200 in losses, saving ~₹630 in STCG tax."

---

### TASK 9 — Trades Page Redesign

**File:** `frontend/src/pages/TradesPage.tsx`

#### 9.1 — Filters bar

- Date range picker (from/to)
- Ticker filter (text input)
- Action filter: All · BUY · SELL
- Status filter: All · Filled · Pending · Cancelled

#### 9.2 — Stats row

Above the table:
- Total trades · Win rate · Average P&L per trade · Best trade · Worst trade

#### 9.3 — Table improvements

- Sticky header
- Alternating row colors
- P&L column (computed from `submitted_price` vs `filled_price`)
- Status badge with colors (filled=green, pending=amber, cancelled=grey, rejected=red)
- Row click → expands to show stop_loss / take_profit / query_id / alpaca_order_id

#### 9.4 — Export button

"Export CSV" button — client-side export of visible rows to CSV using `Blob` + `URL.createObjectURL`.

---

### TASK 10 — Agent Runs Page (audit trail)

**File:** `frontend/src/pages/AgentRunsPage.tsx`

The existing `AgentRunHistory.tsx` component is a good start. Expand it.

#### 10.1 — Run timeline view

For each query_id, show a vertical timeline:
```
  ● [9:15:02] Orchestrator started
  ● [9:15:03] Research Agent → 42 articles, sentiment: BULLISH (0.67)
  ● [9:15:05] Quant Agent → RSI: 58.3, MACD: bullish crossover → BUY
  ● [9:15:06] Risk Agent → PASS, qty: 12, SL: ₹234.50
  ● [9:15:07] Execution Agent → Order filled @ ₹238.90
  ● [9:15:07] Final Signal: BUY (confidence 78%)
```

#### 10.2 — Latency visualization

Horizontal bar chart showing each agent's latency_ms. Helps identify slow agents.

#### 10.3 — Error surface

Runs with `status=error` highlighted in red with expandable error message.

---

### TASK 11 — Global Responsiveness Pass

After all pages are built, do a dedicated mobile responsiveness pass.

#### 11.1 — Breakpoint audit

Test every page at: 375px (iPhone SE) · 390px (iPhone 14) · 768px (iPad) · 1024px (laptop) · 1440px (desktop)

#### 11.2 — Table overflow strategy

All tables must have `overflow-x-auto` wrapper. On mobile, show only essential columns (ticker, action, P&L). Add horizontal scroll indicator (fade gradient on right edge).

#### 11.3 — Modal sizing

All modals: `max-h-[90vh] overflow-y-auto` with `w-full max-w-2xl` centering. On mobile: full-height bottom sheet (`fixed bottom-0 rounded-t-2xl`).

#### 11.4 — Touch targets

All interactive elements: minimum `44×44px` touch target. Use `py-3 px-4` minimum for buttons on mobile.

#### 11.5 — Font size floor

Never below `text-xs` (12px) on mobile. Remove `text-[10px]` anywhere it appears.

---

### TASK 12 — Design System & Visual Polish

Apply after all pages are built.

#### 12.1 — Color tokens (add to `index.css`)

```css
:root {
  --color-bg-base: #0f172a;       /* slate-900 */
  --color-bg-surface: #1e293b;    /* slate-800 */
  --color-bg-elevated: #334155;   /* slate-700 */
  --color-border: #334155;
  --color-accent: #6366f1;        /* indigo-500 */
  --color-buy: #10b981;           /* emerald-500 */
  --color-sell: #ef4444;          /* red-500 */
  --color-hold: #f59e0b;          /* amber-500 */
  --color-text-primary: #f1f5f9;
  --color-text-secondary: #94a3b8;
  --color-text-muted: #475569;
}
```

#### 12.2 — Loading skeletons

Replace all `"Loading…"` text with animated skeleton components.

Example for a stat card skeleton:
```tsx
function StatCardSkeleton() {
  return (
    <div className="bg-slate-800 rounded-xl p-4 border border-slate-700 animate-pulse">
      <div className="h-3 w-20 bg-slate-700 rounded mb-3" />
      <div className="h-7 w-32 bg-slate-700 rounded" />
    </div>
  )
}
```

#### 12.3 — Empty state illustrations

Replace all `"No data yet"` text with illustrated empty states:
- Watchlist empty: telescope icon + "Start by searching for a stock"
- News empty: newspaper icon + "No news yet. Click 'Fetch Latest News' above"
- Portfolio empty: briefcase icon + "No open positions"
- Trades empty: activity icon + "No trades placed yet"

All icons should be inline SVG, matching the slate-600 muted color.

#### 12.4 — Micro-interactions

- Signal badge: subtle pulse animation when signal is "fresh" (< 5 min old)
- Portfolio value: counter animation when value updates (react-countup or CSS)
- Card hover: `translate-y-[-2px] shadow-lg` transition
- Button press: `active:scale-95` transition

#### 12.5 — Page transitions

Wrap `<Routes>` with `AnimatePresence` (framer-motion). Each page enters with `opacity-0 → opacity-100` over 150ms.

---

### TASK 13 — PWA & Notifications (optional, high impact)

#### 13.1 — PWA manifest

**File:** `frontend/public/manifest.json`
```json
{
  "name": "Stock Market AI",
  "short_name": "StockAI",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0f172a",
  "theme_color": "#6366f1",
  "icons": [{ "src": "/favicon.svg", "type": "image/svg+xml", "sizes": "any" }]
}
```

Link it in `index.html`: `<link rel="manifest" href="/manifest.json" />`

#### 13.2 — Signal change notifications

When a new signal is generated for a watchlist ticker, show a browser notification:
- "RELIANCE.NS: Signal changed to BUY (confidence 82%)"

Uses `Notification` browser API. Request permission on first visit.

---

## Implementation Priority

| Priority | Task | Impact | Effort |
|---|---|---|---|
| P0 | Task 0 — Fix news page | Fixes broken feature | 1 hour |
| P1 | Task 1 — Router + layout | Unlocks all others | 3 hours |
| P1 | Task 2 — Dashboard | First impression | 4 hours |
| P1 | Task 11 — Responsiveness | Mobile users | 3 hours |
| P2 | Task 3 — Watchlist redesign | Core feature | 2 hours |
| P2 | Task 4 — Candlestick chart | High value for traders | 3 hours |
| P2 | Task 5 — News redesign | Fixes UX after Task 0 | 2 hours |
| P2 | Task 6 — Portfolio redesign | Core feature | 3 hours |
| P3 | Task 7 — FII/DII page | India-specific power | 3 hours |
| P3 | Task 8 — Tax page | India-specific power | 2 hours |
| P3 | Task 9 — Trades redesign | Quality of life | 2 hours |
| P3 | Task 10 — Agent runs | Developer/power user | 2 hours |
| P4 | Task 12 — Design polish | Visual excellence | 3 hours |
| P4 | Task 13 — PWA | Mobile power user | 2 hours |

**Total estimated effort: ~35 hours for full redesign.**
Start with P0+P1+P11 for a working, beautiful, responsive foundation in ~7 hours.
