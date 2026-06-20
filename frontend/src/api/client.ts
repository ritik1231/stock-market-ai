import axios from 'axios'

export const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// --- Types ---

export interface WatchlistItem {
  id: number
  ticker: string
  company: string | null
  sector: string | null
  is_active: boolean
}

export interface QuantIndicators {
  rsi_14: number | null
  macd_line: number | null
  macd_signal: number | null
  macd_hist: number | null
  bb_upper: number | null
  bb_middle: number | null
  bb_lower: number | null
  sma_50: number | null
  sma_200: number | null
  atr_14: number | null
  ema_20: number | null
  volume_sma_20: number | null
  circuit_upper: number | null
  circuit_lower: number | null
  rsi_zone: string | null
  bb_position: string | null
  sma_cross: string | null
  macd_signal_label: string | null
  circuit_alert: string | null
  near_upper_circuit: boolean
  near_lower_circuit: boolean
}

export interface RawOutput {
  research?: {
    sentiment_score: number
    sentiment_label: string
    sentiment_reasoning: string
    rag_answer: string
    article_count: number
    fii_signal: string
    summary?: string
  }
  quant?: {
    indicators: QuantIndicators
    quant_signal: string
    current_price: number
    atr_14: number
    period: string
    interval: string
  }
  risk?: {
    decision: string
    reason: string
    suggested_qty: number
    stop_loss: number
    take_profit: number
  }
  synthesis?: {
    signal: string
    confidence: number
    summary: string
    key_factors: string[]
  }
}

export interface SignalResponse {
  id: number
  query_id: string
  ticker: string
  signal: 'BUY' | 'SELL' | 'HOLD' | string
  confidence: number | null
  quant_signal: string | null
  sentiment_score: number | null
  risk_decision: string | null
  summary: string | null
  raw_output: RawOutput | null
  generated_at: string
}

export interface NewsItem {
  id: number
  ticker: string | null
  headline: string
  source: string | null
  url: string | null
  published_at: string | null
  sentiment_score: number | null
  ingested_at: string | null
}

export interface AnalyzeResponse {
  query_id: string
  ticker: string
  status: string
  poll_url: string
}

export interface AnalysisResult {
  query_id: string
  ticker: string
  status: string
  final_signal: string | null
  confidence: number | null
  summary: string | null
  key_factors: string[] | null
  research_result: Record<string, unknown> | null
  quant_result: Record<string, unknown> | null
  risk_result: Record<string, unknown> | null
  execution_result: Record<string, unknown> | null
}

export interface PositionSchema {
  ticker: string
  qty: number
  avg_entry: number
  current_price: number
  unrealized_pnl: number
  market_value: number
}

export interface PortfolioResponse {
  equity: number
  buying_power: number
  portfolio_value: number
  cash: number
  positions: PositionSchema[]
}

export interface PnlDataPoint {
  date: string
  portfolio_value: number
  daily_pnl: number | null
}

export interface RunSummary {
  query_id: string
  tickers: string[]
  agent_count: number
  latest_status: string
  started_at: string | null
  finished_at: string | null
}

export interface AgentLogDetail {
  id: number
  query_id: string
  agent_name: string
  task_input: Record<string, unknown> | null
  task_output: Record<string, unknown> | null
  status: string
  error_message: string | null
  latency_ms: number | null
  started_at: string | null
  finished_at: string | null
}

// --- API functions ---

export const analyzeStock = (ticker: string, mode = 'signal_only', lookback_days = 7) =>
  api.post<AnalyzeResponse>('/analyze', { ticker, mode, lookback_days }).then(r => r.data)

export const getAnalysisResult = (query_id: string) =>
  api.get<AnalysisResult | { query_id: string; status: string }>(`/analysis/${query_id}`).then(r => r.data)

export const getSignal = (ticker: string) =>
  api.get<SignalResponse>(`/signal/${ticker}`).then(r => r.data)

export interface TradeRecord {
  id: number
  query_id: string | null
  alpaca_order_id: string | null
  ticker: string
  action: string
  qty: number
  submitted_price: number | null
  filled_price: number | null
  stop_loss: number | null
  take_profit: number | null
  status: string | null
  paper_mode: boolean
  submitted_at: string
  filled_at: string | null
}

export interface TradeRequest {
  ticker: string
  action: 'BUY' | 'SELL'
  qty: number
  stop_loss?: number
  take_profit?: number
}

export interface TradeResponse {
  query_id: string
  ticker: string
  order_id: string
  status: string
  filled_price: number | null
  timestamp: string | null
}

export const getWatchlist = () =>
  api.get<WatchlistItem[]>('/watchlist').then(r => r.data)

export const addToWatchlist = (ticker: string, company?: string, sector?: string) =>
  api.post<WatchlistItem>('/watchlist', { ticker, company, sector }).then(r => r.data)

export const removeFromWatchlist = (ticker: string) =>
  api.delete(`/watchlist/${ticker}`)

export const getPortfolio = () =>
  api.get<PortfolioResponse>('/portfolio').then(r => r.data)

export const getPortfolioHistory = (limit = 90) =>
  api.get<PnlDataPoint[]>('/portfolio/history', { params: { limit } }).then(r => r.data)

export const getTrades = (ticker?: string, limit = 50, offset = 0) =>
  api.get<TradeRecord[]>('/trades', { params: { ticker, limit, offset } }).then(r => r.data)

export const placeTrade = (body: TradeRequest) =>
  api.post<TradeResponse>('/trade', body).then(r => r.data)

export interface SearchResult {
  ticker: string
  name: string
  exchange: string
  type: string
}

export const searchStocks = (q: string) =>
  api.get<SearchResult[]>('/search', { params: { q } }).then(r => r.data)

export const getRecentRuns = (limit = 50) =>
  api.get<RunSummary[]>('/runs', { params: { limit } }).then(r => r.data)

export const getQueryLogs = (query_id: string) =>
  api.get<AgentLogDetail[]>(`/query/${query_id}/logs`).then(r => r.data)

export const getNews = (ticker?: string, limit = 50) =>
  api.get<NewsItem[]>('/news', { params: { ticker, limit } }).then(r => r.data)

export const refreshNews = () =>
  api.post<{ ingested: number; tickers: string[] }>('/news/refresh').then(r => r.data)

export interface IndexQuote {
  key: string
  symbol: string
  name: string
  price: number | null
  change: number | null
  change_pct: number | null
  error: string | null
}

export const getMarketIndices = () =>
  api.get<IndexQuote[]>('/market/indices').then(r => r.data)

export interface FiiDiiData {
  date: string
  fii_net_crore: number
  dii_net_crore: number
  signal: 'BULLISH' | 'BEARISH' | 'NEUTRAL'
  interpretation?: string
}

export const getFiiDii = () =>
  api.get<FiiDiiData>('/fii-dii').then(r => r.data)

export interface TaxSummary {
  fy_label: string
  stcg_profit: number
  stcg_loss: number
  ltcg_profit: number
  ltcg_loss: number
  stcg_tax: number
  ltcg_tax: number
  total_tax: number
  trades: TaxTrade[]
}

export interface TaxTrade {
  ticker: string
  action: string
  qty: number
  buy_price: number | null
  sell_price: number | null
  gain: number | null
  gain_type: string | null
  tax_estimate: number | null
  buy_date: string | null
  sell_date: string | null
  days_held: number | null
}
