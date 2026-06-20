import { useState, useEffect, type ReactNode } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getWatchlist,
  getSignal,
  analyzeStock,
  getAnalysisResult,
  addToWatchlist,
  removeFromWatchlist,
  type SignalResponse,
} from '../api/client'
import StockSearch from './StockSearch'

type SignalLabel = 'BUY' | 'SELL' | 'HOLD' | string

const signalBadgeClass = (s: SignalLabel) => {
  if (s === 'BUY') return 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
  if (s === 'SELL') return 'bg-red-500/20 text-red-400 border border-red-500/40'
  if (s === 'HOLD') return 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
  return 'bg-slate-700/60 text-slate-400 border border-slate-600/40'
}

// Legacy signalColor used only in modal
const signalColor = (s: SignalLabel) => {
  if (s === 'BUY') return 'bg-emerald-500 text-white'
  if (s === 'SELL') return 'bg-red-500 text-white'
  if (s === 'HOLD') return 'bg-yellow-400 text-black'
  return 'bg-slate-500 text-white'
}

const cardBorderClass = (s?: SignalLabel) => {
  if (s === 'BUY') return 'border-emerald-500/30 hover:border-emerald-500/50'
  if (s === 'SELL') return 'border-red-500/30 hover:border-red-500/50'
  return 'border-slate-700/60 hover:border-slate-600'
}

function Toast({ message, type = 'info', onClose }: { message: string; type?: 'info' | 'error'; onClose: () => void }) {
  useEffect(() => {
    const t = setTimeout(onClose, 5000)
    return () => clearTimeout(t)
  }, [onClose])
  return (
    <div className={`fixed bottom-4 right-4 px-4 py-3 rounded-lg shadow-xl max-w-sm z-50 text-sm flex items-start gap-3 ${type === 'error' ? 'bg-red-900 text-red-200 border border-red-700' : 'bg-slate-700 text-white'}`}>
      <span className="flex-1">{message}</span>
      <button onClick={onClose} className="opacity-60 hover:opacity-100 flex-shrink-0">✕</button>
    </div>
  )
}

type ModalTab = 'overview' | 'technical' | 'research' | 'risk'

function IndBar({ label, value, min, max, good, bad, fmt }: {
  label: string; value: number | null; min: number; max: number
  good?: [number, number]; bad?: [number, number]; fmt?: (v: number) => string
}) {
  if (value == null) return null
  const pct = Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100))
  const fmtFn = fmt ?? ((v: number) => v.toFixed(2))
  const inGood = good && value >= good[0] && value <= good[1]
  const inBad = bad && value >= bad[0] && value <= bad[1]
  const color = inGood ? 'bg-emerald-500' : inBad ? 'bg-red-500' : 'bg-indigo-500'
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-slate-400">{label}</span>
        <span className={`font-mono font-medium ${inGood ? 'text-emerald-400' : inBad ? 'text-red-400' : 'text-white'}`}>{fmtFn(value)}</span>
      </div>
      <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function Explain({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="bg-slate-800/60 border border-slate-700 rounded-lg p-3 text-xs text-slate-400 leading-relaxed">
      <span className="text-slate-300 font-medium">{title}: </span>{children}
    </div>
  )
}

function SignalModal({ ticker, signal, onClose }: { ticker: string; signal: SignalResponse; onClose: () => void }) {
  const [tab, setTab] = useState<ModalTab>('overview')

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  const ro = signal.raw_output
  const ind = ro?.quant?.indicators
  const research = ro?.research
  const risk = ro?.risk
  const synthesis = ro?.synthesis

  const tabs: { id: ModalTab; label: string }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'technical', label: 'Technical' },
    { id: 'research', label: 'Research' },
    { id: 'risk', label: 'Risk' },
  ]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <div className="relative bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[88vh] flex flex-col" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between gap-3 px-6 pt-5 pb-4 border-b border-slate-700 flex-shrink-0">
          <div className="flex items-center gap-3">
            <span className="font-bold text-white text-xl font-mono tracking-wider">{ticker}</span>
            <span className={`text-sm font-bold px-3 py-1 rounded-full ${signalColor(signal.signal)}`}>{signal.signal}</span>
            {signal.confidence != null && (
              <span className="text-xs text-slate-400">Confidence: <span className="text-white font-medium">{(signal.confidence * 100).toFixed(0)}%</span></span>
            )}
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-2xl leading-none transition-colors flex-shrink-0">✕</button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-700 px-6 flex-shrink-0">
          {tabs.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`py-2.5 px-3 text-sm border-b-2 -mb-px transition-colors ${tab === t.id ? 'border-indigo-500 text-white' : 'border-transparent text-slate-400 hover:text-slate-200'}`}>
              {t.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="overflow-y-auto flex-1 p-6 flex flex-col gap-4">

          {/* OVERVIEW TAB */}
          {tab === 'overview' && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-slate-800 rounded-xl p-4">
                  <p className="text-xs text-slate-400 mb-1">Final Signal</p>
                  <span className={`text-lg font-bold px-3 py-1 rounded-full inline-block ${signalColor(signal.signal)}`}>{signal.signal}</span>
                  <Explain title="" >BUY = AI recommends buying. SELL = consider selling. HOLD = no action yet.</Explain>
                </div>
                <div className="bg-slate-800 rounded-xl p-4">
                  <p className="text-xs text-slate-400 mb-1">Confidence</p>
                  <p className="text-2xl font-bold text-white">{signal.confidence != null ? `${(signal.confidence * 100).toFixed(0)}%` : '—'}</p>
                  <p className="text-xs text-slate-500 mt-1">How aligned are the 3 agents (research + quant + risk)</p>
                </div>
                <div className="bg-slate-800 rounded-xl p-4">
                  <p className="text-xs text-slate-400 mb-1">Sentiment Score</p>
                  <p className="text-2xl font-bold text-white">{signal.sentiment_score?.toFixed(2) ?? '—'}</p>
                  <p className="text-xs text-slate-500 mt-1">−1 (very bearish) → 0 (neutral) → +1 (very bullish). Based on news &amp; filings.</p>
                </div>
                <div className="bg-slate-800 rounded-xl p-4">
                  <p className="text-xs text-slate-400 mb-1">Risk Decision</p>
                  <p className={`text-2xl font-bold ${signal.risk_decision === 'PASS' ? 'text-emerald-400' : 'text-red-400'}`}>{signal.risk_decision ?? '—'}</p>
                  <p className="text-xs text-slate-500 mt-1">PASS = position sizing approved. BLOCK = risk too high to trade.</p>
                </div>
              </div>

              {synthesis?.key_factors && synthesis.key_factors.length > 0 && (
                <div className="bg-slate-800 rounded-xl p-4">
                  <p className="text-xs text-slate-400 mb-3">Key Factors Driving This Signal</p>
                  <ul className="space-y-1.5">
                    {synthesis.key_factors.map((f, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-slate-200">
                        <span className="text-indigo-400 mt-0.5 flex-shrink-0">→</span>{f}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {signal.summary && (
                <div className="bg-slate-800 rounded-xl p-4">
                  <p className="text-xs text-slate-400 mb-2">AI Summary</p>
                  <p className="text-sm text-slate-200 leading-relaxed">{signal.summary}</p>
                </div>
              )}

              <p className="text-xs text-slate-500">Generated {new Date(signal.generated_at).toLocaleString()}</p>
            </>
          )}

          {/* TECHNICAL TAB */}
          {tab === 'technical' && (
            <>
              {ro?.quant ? (
                <>
                  <div className="grid grid-cols-3 gap-3">
                    <div className="bg-slate-800 rounded-xl p-3 text-center">
                      <p className="text-xs text-slate-400">Current Price</p>
                      <p className="text-lg font-bold text-white font-mono">₹{ro.quant.current_price?.toFixed(2)}</p>
                    </div>
                    <div className="bg-slate-800 rounded-xl p-3 text-center">
                      <p className="text-xs text-slate-400">Quant Signal</p>
                      <p className={`text-lg font-bold ${ro.quant.quant_signal === 'BUY' ? 'text-emerald-400' : ro.quant.quant_signal === 'SELL' ? 'text-red-400' : 'text-yellow-400'}`}>{ro.quant.quant_signal}</p>
                    </div>
                    <div className="bg-slate-800 rounded-xl p-3 text-center">
                      <p className="text-xs text-slate-400">ATR (volatility)</p>
                      <p className="text-lg font-bold text-white font-mono">₹{ro.quant.atr_14?.toFixed(2)}</p>
                    </div>
                  </div>

                  {ind && (
                    <div className="bg-slate-800 rounded-xl p-4 flex flex-col gap-4">
                      <p className="text-xs text-slate-400 font-medium uppercase tracking-wider">Momentum</p>
                      <IndBar label="RSI (14)" value={ind.rsi_14} min={0} max={100} good={[40, 60]} bad={[70, 100]} fmt={v => v.toFixed(1)} />
                      <Explain title="RSI">Relative Strength Index. Below 30 = oversold (potential BUY). Above 70 = overbought (potential SELL). 30–70 = neutral zone.</Explain>

                      <IndBar label="MACD Line" value={ind.macd_line} min={-20} max={20} good={[0.5, 20]} bad={[-20, -0.5]} />
                      <IndBar label="MACD Signal" value={ind.macd_signal} min={-20} max={20} good={[0.5, 20]} bad={[-20, -0.5]} />
                      <IndBar label="MACD Histogram" value={ind.macd_hist} min={-10} max={10} good={[0.1, 10]} bad={[-10, -0.1]} />
                      <Explain title="MACD">Moving Average Convergence Divergence. When MACD Line crosses above Signal Line = bullish. When histogram turns positive = momentum is building.</Explain>

                      <p className="text-xs text-slate-400 font-medium uppercase tracking-wider pt-2">Trend &amp; Bands</p>
                      {ind.bb_upper != null && ind.bb_lower != null && ind.bb_middle != null && ro.quant.current_price != null && (
                        <>
                          <div className="flex justify-between text-xs mb-1">
                            <span className="text-slate-400">Bollinger Bands</span>
                            <span className="text-slate-300 font-mono">₹{ind.bb_lower.toFixed(1)} / ₹{ind.bb_middle.toFixed(1)} / ₹{ind.bb_upper.toFixed(1)}</span>
                          </div>
                          <div className="relative h-6 bg-slate-700 rounded-full overflow-hidden">
                            <div className="absolute inset-0 bg-indigo-900/40 rounded-full" />
                            {(() => {
                              const range = ind.bb_upper - ind.bb_lower
                              const pricePct = ((ro.quant.current_price - ind.bb_lower) / range) * 100
                              return <div className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full shadow" style={{ left: `${Math.min(95, Math.max(5, pricePct))}%` }} />
                            })()}
                          </div>
                          <Explain title="Bollinger Bands">Price envelope ±2 standard deviations from 20-day MA. Price near lower band = cheap (potential BUY). Near upper band = expensive (potential SELL). Current position: <span className="text-white">{ind.bb_position}</span>.</Explain>
                        </>
                      )}

                      <IndBar label="EMA 20" value={ind.ema_20} min={(ind.ema_20 ?? 0) * 0.9} max={(ind.ema_20 ?? 0) * 1.1} fmt={v => `₹${v.toFixed(1)}`} />
                      <IndBar label="SMA 50" value={ind.sma_50} min={(ind.sma_50 ?? 0) * 0.9} max={(ind.sma_50 ?? 0) * 1.1} fmt={v => `₹${v.toFixed(1)}`} />
                      <Explain title="Moving Averages">EMA 20 = 20-day exponential average (reacts fast). SMA 50 = 50-day simple average (slower trend). Price above both = uptrend. Below both = downtrend.</Explain>

                      {(ind.circuit_upper != null || ind.circuit_lower != null) && (
                        <>
                          <p className="text-xs text-slate-400 font-medium uppercase tracking-wider pt-2">NSE Circuit Breakers</p>
                          <div className="grid grid-cols-2 gap-2">
                            <div className="bg-slate-700 rounded-lg p-2 text-center">
                              <p className="text-xs text-slate-400">Upper Circuit</p>
                              <p className="text-emerald-400 font-mono text-sm">₹{ind.circuit_upper?.toFixed(2)}</p>
                            </div>
                            <div className="bg-slate-700 rounded-lg p-2 text-center">
                              <p className="text-xs text-slate-400">Lower Circuit</p>
                              <p className="text-red-400 font-mono text-sm">₹{ind.circuit_lower?.toFixed(2)}</p>
                            </div>
                          </div>
                          <Explain title="Circuit Breakers">NSE auto-halts trading if price hits these limits. Near upper circuit = extreme buying pressure. Near lower circuit = extreme sell-off.</Explain>
                          {(ind.near_upper_circuit || ind.near_lower_circuit) && (
                            <p className={`text-xs font-medium ${ind.near_upper_circuit ? 'text-emerald-400' : 'text-red-400'}`}>
                              ⚠ Price is near the {ind.near_upper_circuit ? 'upper' : 'lower'} circuit breaker
                            </p>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </>
              ) : (
                <p className="text-slate-400 text-sm">No technical data available. Run analysis first.</p>
              )}
            </>
          )}

          {/* RESEARCH TAB */}
          {tab === 'research' && (
            <>
              {research ? (
                <>
                  <div className="grid grid-cols-3 gap-3">
                    <div className="bg-slate-800 rounded-xl p-3 text-center">
                      <p className="text-xs text-slate-400">Sentiment</p>
                      <p className={`text-lg font-bold ${research.sentiment_score > 0.1 ? 'text-emerald-400' : research.sentiment_score < -0.1 ? 'text-red-400' : 'text-yellow-400'}`}>{research.sentiment_label}</p>
                      <p className="text-xs text-slate-500 font-mono">{research.sentiment_score.toFixed(2)}</p>
                    </div>
                    <div className="bg-slate-800 rounded-xl p-3 text-center">
                      <p className="text-xs text-slate-400">Articles Analysed</p>
                      <p className="text-lg font-bold text-white">{research.article_count}</p>
                    </div>
                    <div className="bg-slate-800 rounded-xl p-3 text-center">
                      <p className="text-xs text-slate-400">FII Signal</p>
                      <p className="text-lg font-bold text-slate-200">{research.fii_signal ?? '—'}</p>
                    </div>
                  </div>

                  <div className="bg-slate-800 rounded-xl p-4">
                    <p className="text-xs text-slate-400 mb-2">Why this sentiment?</p>
                    <p className="text-sm text-slate-200 leading-relaxed">{research.sentiment_reasoning}</p>
                  </div>

                  <Explain title="How sentiment is calculated">The Research Agent fetches the latest news from NewsAPI and Yahoo RSS feeds, then asks the Groq LLM (Llama 3.3 70B) to score each batch of headlines for the company. Score ranges from −1 (very negative) to +1 (very positive). It also checks FII/DII institutional flow signals.</Explain>

                  {research.summary && (
                    <div className="bg-slate-800 rounded-xl p-4">
                      <p className="text-xs text-slate-400 mb-2">News &amp; Market Context ({research.article_count} articles)</p>
                      <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-line">{research.summary}</p>
                    </div>
                  )}

                  <div className="bg-slate-800 rounded-xl p-4">
                    <p className="text-xs text-slate-400 mb-2">RAG-based Filing Analysis</p>
                    <p className="text-xs text-slate-500 mb-2">From SEC/company filings stored in vector DB (pgvector)</p>
                    <p className="text-sm text-slate-300 leading-relaxed">{research.rag_answer}</p>
                  </div>

                  <Explain title="What is RAG?">Retrieval-Augmented Generation. Past company filings and earnings transcripts are split into chunks and stored as vector embeddings in PostgreSQL (pgvector). When you run analysis, the most relevant chunks are fetched and given to the AI as context — so it can answer questions about the company based on real documents, not just training data.</Explain>
                </>
              ) : (
                <p className="text-slate-400 text-sm">No research data available. Run analysis first.</p>
              )}
            </>
          )}

          {/* RISK TAB */}
          {tab === 'risk' && (
            <>
              {risk ? (
                <>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-slate-800 rounded-xl p-4">
                      <p className="text-xs text-slate-400 mb-1">Decision</p>
                      <p className={`text-2xl font-bold ${risk.decision === 'PASS' ? 'text-emerald-400' : 'text-red-400'}`}>{risk.decision}</p>
                    </div>
                    <div className="bg-slate-800 rounded-xl p-4">
                      <p className="text-xs text-slate-400 mb-1">Suggested Qty</p>
                      <p className="text-2xl font-bold text-white">{risk.suggested_qty} shares</p>
                    </div>
                    <div className="bg-slate-800 rounded-xl p-4">
                      <p className="text-xs text-slate-400 mb-1">Stop Loss</p>
                      <p className="text-xl font-bold text-red-400 font-mono">₹{risk.stop_loss?.toFixed(2)}</p>
                      <p className="text-xs text-slate-500 mt-1">Exit trade here to cap losses</p>
                    </div>
                    <div className="bg-slate-800 rounded-xl p-4">
                      <p className="text-xs text-slate-400 mb-1">Take Profit</p>
                      <p className="text-xl font-bold text-emerald-400 font-mono">₹{risk.take_profit?.toFixed(2)}</p>
                      <p className="text-xs text-slate-500 mt-1">Exit trade here to lock in gains</p>
                    </div>
                  </div>

                  <div className="bg-slate-800 rounded-xl p-4">
                    <p className="text-xs text-slate-400 mb-2">Risk Agent Reasoning</p>
                    <p className="text-sm text-slate-200">{risk.reason}</p>
                  </div>

                  <Explain title="How stop loss is calculated">Stop loss = Current Price − (ATR × 2). ATR (Average True Range) measures daily price volatility. Multiplying by 2 gives a buffer that avoids being stopped out by normal daily swings.</Explain>
                  <Explain title="How take profit is calculated">Take profit = Current Price + (ATR × 3). Risk:reward ratio of 1:1.5. For every ₹1 you risk, you target ₹1.5 in profit.</Explain>
                  <Explain title="Position sizing">The Risk Agent uses confidence score from Research + ATR-based volatility to decide how many shares to buy. Higher confidence + lower volatility = larger position allowed.</Explain>
                  <Explain title="PASS vs BLOCK">PASS = risk parameters are acceptable, trade can proceed. BLOCK = signal is HOLD/too weak, or risk:reward is unfavorable — no trade is placed.</Explain>
                </>
              ) : (
                <p className="text-slate-400 text-sm">No risk data available. Run analysis first.</p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function TickerSignalCard({ ticker }: { ticker: string }) {
  const qc = useQueryClient()
  const [toast, setToast] = useState<{ msg: string; type?: 'info' | 'error' } | null>(null)
  const [polling, setPolling] = useState<string | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [showTrashIcon, setShowTrashIcon] = useState(false)

  const { data: signal, isLoading } = useQuery<SignalResponse>({
    queryKey: ['signal', ticker],
    queryFn: () => getSignal(ticker),
    retry: false,
    staleTime: 30_000,
  })

  useEffect(() => {
    if (!polling) return
    let done = false
    const interval = setInterval(async () => {
      try {
        const res = await getAnalysisResult(polling)
        if ('status' in res && res.status === 'completed') {
          clearInterval(interval)
          done = true
          setPolling(null)
          qc.invalidateQueries({ queryKey: ['signal', ticker] })
          const r = res as { final_signal?: string; summary?: string }
          setToast({ msg: `${ticker}: ${r.final_signal ?? 'done'} — ${(r.summary ?? '').slice(0, 120)}` })
        }
      } catch {
        // still pending
      }
    }, 3000)
    return () => { if (!done) clearInterval(interval) }
  }, [polling, ticker, qc])

  const { mutate: runAnalysis, isPending } = useMutation({
    mutationFn: () => analyzeStock(ticker, 'signal_only'),
    onSuccess: (data) => setPolling(data.query_id),
    onError: () => setToast({ msg: 'Analysis failed. Is Celery running?', type: 'error' }),
  })

  const { mutate: doRemove, isPending: removing } = useMutation({
    mutationFn: () => removeFromWatchlist(ticker),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['watchlist'] }),
  })

  const hasSignal = !!signal
  const isAnalyzing = isPending || !!polling

  return (
    <>
      {showModal && signal && <SignalModal ticker={ticker} signal={signal} onClose={() => setShowModal(false)} />}

      <div
        className={`bg-slate-800/60 rounded-xl border transition-colors flex flex-col ${cardBorderClass(signal?.signal)}`}
        onMouseEnter={() => setShowTrashIcon(true)}
        onMouseLeave={() => setShowTrashIcon(false)}
      >
        {/* Card header: ticker + signal badge + menu */}
        <div className="flex items-center justify-between gap-2 px-4 pt-4 pb-3">
          <span className="font-bold text-white font-mono tracking-wider text-base uppercase">{ticker}</span>
          <div className="flex items-center gap-2">
            {isLoading ? (
              <span className="text-slate-500 text-xs">—</span>
            ) : hasSignal ? (
              <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full ${signalBadgeClass(signal.signal)}`}>
                {signal.signal}
              </span>
            ) : (
              <span className="text-slate-500 text-xs bg-slate-700/60 border border-slate-600/40 px-2.5 py-0.5 rounded-full">No signal</span>
            )}
            <button
              onClick={() => doRemove()}
              disabled={removing}
              title="Remove from watchlist"
              className={`transition-opacity text-slate-500 hover:text-red-400 disabled:opacity-30 ${showTrashIcon ? 'opacity-100' : 'opacity-0'}`}
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
        </div>

        {hasSignal ? (
          <>
            {/* Current price */}
            {signal.raw_output?.quant?.current_price != null && (
              <div className="px-4 pb-2">
                <span className="text-white font-mono text-xl font-semibold">
                  ₹{signal.raw_output.quant.current_price.toFixed(2)}
                </span>
              </div>
            )}

            {/* Divider */}
            <div className="border-t border-slate-700/50 mx-4" />

            {/* Metrics row */}
            <div className="flex flex-wrap gap-x-4 gap-y-1 px-4 py-2.5 text-xs">
              {signal.confidence != null && (
                <span className="text-slate-400">
                  Confidence <span className="text-slate-200 font-medium font-mono">{(signal.confidence * 100).toFixed(0)}%</span>
                </span>
              )}
              {signal.sentiment_score != null && (
                <span className="text-slate-400">
                  Sentiment <span className="text-slate-200 font-medium font-mono">{signal.sentiment_score.toFixed(2)}</span>
                </span>
              )}
              {signal.raw_output?.quant?.atr_14 != null && (
                <span className="text-slate-400">
                  ATR <span className="text-slate-200 font-medium font-mono">{signal.raw_output.quant.atr_14.toFixed(1)}</span>
                </span>
              )}
            </div>

            {/* Divider */}
            <div className="border-t border-slate-700/50 mx-4" />

            {/* Summary */}
            {signal.summary && (
              <div className="px-4 pt-3 pb-1">
                <p
                  className={`text-xs text-slate-400 leading-relaxed cursor-pointer hover:text-slate-300 transition-colors ${expanded ? '' : 'line-clamp-3'}`}
                  onClick={() => setExpanded(v => !v)}
                >
                  {signal.summary}
                </p>
                <button
                  onClick={() => setShowModal(true)}
                  className="text-xs text-indigo-400 hover:text-indigo-300 mt-1.5 inline-block transition-colors"
                >
                  View full analysis →
                </button>
              </div>
            )}

            {/* Divider */}
            <div className="border-t border-slate-700/50 mx-4 mt-2" />

            {/* Footer: analyze button + date */}
            <div className="flex items-center justify-between gap-2 px-4 py-3">
              <button
                onClick={() => runAnalysis()}
                disabled={isAnalyzing}
                className="bg-indigo-600/80 hover:bg-indigo-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-xs px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5"
              >
                {isAnalyzing ? (
                  <>
                    <span className="animate-spin inline-block w-3 h-3 border border-white border-t-transparent rounded-full" />
                    Analyzing…
                  </>
                ) : (
                  <>▶ Analyze</>
                )}
              </button>
              {signal.generated_at && (
                <span className="text-xs text-slate-600 font-mono">
                  {new Date(signal.generated_at).toLocaleDateString('en-IN')}
                </span>
              )}
            </div>
          </>
        ) : (
          /* No signal yet */
          <div className="px-4 pb-4 flex flex-col gap-3">
            <p className="text-xs text-slate-500">No analysis run yet</p>
            <button
              onClick={() => runAnalysis()}
              disabled={isAnalyzing}
              className="bg-indigo-600/80 hover:bg-indigo-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-xs px-3 py-1.5 rounded-lg transition-colors self-start flex items-center gap-1.5"
            >
              {isAnalyzing ? (
                <>
                  <span className="animate-spin inline-block w-3 h-3 border border-white border-t-transparent rounded-full" />
                  Analyzing…
                </>
              ) : (
                <>▶ Run Analysis</>
              )}
            </button>
          </div>
        )}
      </div>
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </>
  )
}

export default function WatchlistPanel() {
  const qc = useQueryClient()
  const [toast, setToast] = useState<{ msg: string; type?: 'info' | 'error' } | null>(null)

  const { data: watchlist, isLoading, isError } = useQuery({
    queryKey: ['watchlist'],
    queryFn: getWatchlist,
    refetchInterval: 30_000,
  })

  const { mutate: addTicker, isPending: adding } = useMutation({
    mutationFn: ({ ticker, name }: { ticker: string; name: string }) =>
      addToWatchlist(ticker, name),
    onSuccess: (item) => {
      qc.invalidateQueries({ queryKey: ['watchlist'] })
      setToast({ msg: `${item.ticker} added to watchlist` })
    },
    onError: () => setToast({ msg: 'Failed to add ticker.', type: 'error' }),
  })

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-white">Watchlist</h2>
        <span className="text-xs text-slate-500">{watchlist?.length ?? 0} tickers</span>
      </div>

      {/* Search + add */}
      <div className="flex gap-2 items-center">
        <StockSearch
          onSelect={(ticker, name) => {
            if (!adding) addTicker({ ticker, name })
          }}
        />
        {adding && <span className="text-xs text-slate-400 flex-shrink-0">Adding…</span>}
      </div>

      {isLoading && <p className="text-slate-400 text-sm">Loading watchlist…</p>}
      {isError && <p className="text-red-400 text-sm">Failed to load watchlist.</p>}

      {watchlist && watchlist.length === 0 && (
        <div className="bg-slate-800/60 border border-dashed border-slate-700 rounded-xl p-8 text-center">
          <p className="text-slate-400 text-sm">No tickers yet. Search above to add stocks.</p>
          <p className="text-slate-500 text-xs mt-1">Try searching "Tata", "Reliance", "Infosys"…</p>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {watchlist?.map((item) => (
          <TickerSignalCard key={item.id} ticker={item.ticker} />
        ))}
      </div>

      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  )
}
