import { useState, useEffect, type ReactNode } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import toast from 'react-hot-toast'
import {
  getWatchlist,
  getSignal,
  analyzeStock,
  getAnalysisResult,
  addToWatchlist,
  removeFromWatchlist,
  type SignalResponse,
} from '../api/client'
import StockSearch from '../components/StockSearch'
import { CardSkeleton } from '../components/ui/Skeleton'

type SignalLabel = 'BUY' | 'SELL' | 'HOLD' | string
type Filter = 'ALL' | 'BUY' | 'SELL' | 'HOLD' | 'NONE'

const signalBadge = (s: SignalLabel) => {
  if (s === 'BUY') return 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
  if (s === 'SELL') return 'bg-red-500/15 text-red-400 border border-red-500/30'
  if (s === 'HOLD') return 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
  return 'bg-slate-700/60 text-slate-400 border border-slate-600/40'
}

const signalPill = (s: SignalLabel) => {
  if (s === 'BUY') return 'bg-emerald-500 text-white'
  if (s === 'SELL') return 'bg-red-500 text-white'
  if (s === 'HOLD') return 'bg-amber-400 text-black'
  return 'bg-slate-500 text-white'
}

const cardBorder = (s?: SignalLabel) => {
  if (s === 'BUY') return 'border-emerald-500/25 hover:border-emerald-500/50'
  if (s === 'SELL') return 'border-red-500/25 hover:border-red-500/50'
  return 'border-slate-800 hover:border-slate-700'
}

function Explain({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-3 text-xs text-slate-400 leading-relaxed">
      <span className="text-slate-300 font-medium">{title}: </span>{children}
    </div>
  )
}

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
        <span className={clsx('font-mono font-medium', inGood ? 'text-emerald-400' : inBad ? 'text-red-400' : 'text-white')}>
          {fmtFn(value)}
        </span>
      </div>
      <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
        <div className={clsx('h-full rounded-full', color)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

type ModalTab = 'overview' | 'technical' | 'research' | 'risk'

function SignalModal({ ticker, signal, onClose }: { ticker: string; signal: SignalResponse; onClose: () => void }) {
  const [tab, setTab] = useState<ModalTab>('overview')

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', h)
    return () => document.removeEventListener('keydown', h)
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
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <div
        className="relative bg-[#0d1424] border border-slate-700/50 rounded-t-2xl sm:rounded-2xl shadow-2xl w-full sm:max-w-2xl max-h-[92vh] flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        {/* Handle (mobile) */}
        <div className="sm:hidden w-10 h-1 bg-slate-700 rounded-full mx-auto mt-3 mb-1 flex-shrink-0" />

        {/* Header */}
        <div className="flex items-center justify-between gap-3 px-5 pt-4 pb-4 border-b border-slate-800 flex-shrink-0">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="font-bold text-white text-xl font-mono">{ticker}</span>
            <span className={clsx('text-sm font-bold px-3 py-1 rounded-full', signalPill(signal.signal))}>{signal.signal}</span>
            {signal.confidence != null && (
              <span className="text-xs text-slate-400">Confidence: <span className="text-white font-medium">{(signal.confidence * 100).toFixed(0)}%</span></span>
            )}
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors text-xl leading-none flex-shrink-0">✕</button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-800 px-5 flex-shrink-0 overflow-x-auto">
          {tabs.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={clsx(
                'py-2.5 px-3 text-sm border-b-2 -mb-px transition-colors flex-shrink-0',
                tab === t.id ? 'border-indigo-500 text-white' : 'border-transparent text-slate-400 hover:text-slate-200'
              )}>
              {t.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="overflow-y-auto flex-1 p-5 flex flex-col gap-4">
          {tab === 'overview' && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-slate-900 rounded-xl p-4 border border-slate-800">
                  <p className="text-xs text-slate-500 mb-1">Final Signal</p>
                  <span className={clsx('text-lg font-bold px-3 py-1 rounded-full inline-block', signalPill(signal.signal))}>{signal.signal}</span>
                </div>
                <div className="bg-slate-900 rounded-xl p-4 border border-slate-800">
                  <p className="text-xs text-slate-500 mb-1">Confidence</p>
                  <p className="text-2xl font-bold text-white">{signal.confidence != null ? `${(signal.confidence * 100).toFixed(0)}%` : '—'}</p>
                  <p className="text-xs text-slate-600 mt-1">Research + Quant + Risk alignment</p>
                </div>
                <div className="bg-slate-900 rounded-xl p-4 border border-slate-800">
                  <p className="text-xs text-slate-500 mb-1">Sentiment</p>
                  <p className="text-2xl font-bold text-white">{signal.sentiment_score?.toFixed(2) ?? '—'}</p>
                  <p className="text-xs text-slate-600 mt-1">−1 bearish → +1 bullish</p>
                </div>
                <div className="bg-slate-900 rounded-xl p-4 border border-slate-800">
                  <p className="text-xs text-slate-500 mb-1">Risk Decision</p>
                  <p className={clsx('text-2xl font-bold', signal.risk_decision === 'PASS' ? 'text-emerald-400' : 'text-red-400')}>
                    {signal.risk_decision ?? '—'}
                  </p>
                  <p className="text-xs text-slate-600 mt-1">PASS = trade approved</p>
                </div>
              </div>
              {synthesis?.key_factors && synthesis.key_factors.length > 0 && (
                <div className="bg-slate-900 rounded-xl p-4 border border-slate-800">
                  <p className="text-xs text-slate-500 mb-3">Key Factors</p>
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
                <div className="bg-slate-900 rounded-xl p-4 border border-slate-800">
                  <p className="text-xs text-slate-500 mb-2">AI Summary</p>
                  <p className="text-sm text-slate-200 leading-relaxed">{signal.summary}</p>
                </div>
              )}
              <p className="text-xs text-slate-600">Generated {new Date(signal.generated_at).toLocaleString('en-IN')}</p>
            </>
          )}

          {tab === 'technical' && (
            <>
              {ro?.quant ? (
                <>
                  <div className="grid grid-cols-3 gap-3">
                    <div className="bg-slate-900 rounded-xl p-3 text-center border border-slate-800">
                      <p className="text-xs text-slate-500">Price</p>
                      <p className="text-lg font-bold text-white font-mono">₹{ro.quant.current_price?.toFixed(2)}</p>
                    </div>
                    <div className="bg-slate-900 rounded-xl p-3 text-center border border-slate-800">
                      <p className="text-xs text-slate-500">Quant Signal</p>
                      <p className={clsx('text-lg font-bold', ro.quant.quant_signal === 'BUY' ? 'text-emerald-400' : ro.quant.quant_signal === 'SELL' ? 'text-red-400' : 'text-yellow-400')}>
                        {ro.quant.quant_signal}
                      </p>
                    </div>
                    <div className="bg-slate-900 rounded-xl p-3 text-center border border-slate-800">
                      <p className="text-xs text-slate-500">ATR (volatility)</p>
                      <p className="text-lg font-bold text-white font-mono">₹{ro.quant.atr_14?.toFixed(2)}</p>
                    </div>
                  </div>
                  {ind && (
                    <div className="bg-slate-900 rounded-xl p-4 border border-slate-800 flex flex-col gap-4">
                      <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">Momentum</p>
                      <IndBar label="RSI (14)" value={ind.rsi_14} min={0} max={100} good={[40, 60]} bad={[70, 100]} fmt={v => v.toFixed(1)} />
                      <Explain title="RSI">Below 30 = oversold (potential BUY). Above 70 = overbought (potential SELL). 30–70 = neutral.</Explain>
                      <IndBar label="MACD Line" value={ind.macd_line} min={-20} max={20} good={[0.5, 20]} bad={[-20, -0.5]} />
                      <IndBar label="MACD Histogram" value={ind.macd_hist} min={-10} max={10} good={[0.1, 10]} bad={[-10, -0.1]} />
                      <Explain title="MACD">MACD Line above Signal Line = bullish momentum. Positive histogram = building strength.</Explain>
                      <p className="text-xs text-slate-500 font-medium uppercase tracking-wider pt-1">Trend</p>
                      {ind.bb_upper != null && ind.bb_lower != null && ind.bb_middle != null && ro.quant.current_price != null && (
                        <>
                          <div className="flex justify-between text-xs mb-1">
                            <span className="text-slate-400">Bollinger Bands</span>
                            <span className="text-slate-300 font-mono">₹{ind.bb_lower.toFixed(0)} / ₹{ind.bb_middle.toFixed(0)} / ₹{ind.bb_upper.toFixed(0)}</span>
                          </div>
                          <div className="relative h-5 bg-slate-800 rounded-full overflow-hidden">
                            {(() => {
                              const range = ind.bb_upper - ind.bb_lower
                              const pricePct = ((ro.quant.current_price - ind.bb_lower) / range) * 100
                              return <div className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full shadow" style={{ left: `${Math.min(92, Math.max(8, pricePct))}%` }} />
                            })()}
                          </div>
                          <Explain title="Bollinger Bands">Price near lower band = potentially undervalued. Near upper band = potentially overvalued. Position: <span className="text-white">{ind.bb_position}</span></Explain>
                        </>
                      )}
                      {(ind.circuit_upper != null || ind.circuit_lower != null) && (
                        <>
                          <p className="text-xs text-slate-500 font-medium uppercase tracking-wider pt-1">NSE Circuit Breakers</p>
                          <div className="grid grid-cols-2 gap-2">
                            <div className="bg-slate-800 rounded-lg p-2 text-center">
                              <p className="text-xs text-slate-500">Upper Circuit</p>
                              <p className="text-emerald-400 font-mono text-sm">₹{ind.circuit_upper?.toFixed(2)}</p>
                            </div>
                            <div className="bg-slate-800 rounded-lg p-2 text-center">
                              <p className="text-xs text-slate-500">Lower Circuit</p>
                              <p className="text-red-400 font-mono text-sm">₹{ind.circuit_lower?.toFixed(2)}</p>
                            </div>
                          </div>
                          {(ind.near_upper_circuit || ind.near_lower_circuit) && (
                            <p className={clsx('text-xs font-medium', ind.near_upper_circuit ? 'text-emerald-400' : 'text-red-400')}>
                              ⚡ Price is near the {ind.near_upper_circuit ? 'upper' : 'lower'} circuit breaker
                            </p>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </>
              ) : <p className="text-slate-400 text-sm">No technical data. Run analysis first.</p>}
            </>
          )}

          {tab === 'research' && (
            <>
              {research ? (
                <>
                  <div className="grid grid-cols-3 gap-3">
                    <div className="bg-slate-900 rounded-xl p-3 text-center border border-slate-800">
                      <p className="text-xs text-slate-500">Sentiment</p>
                      <p className={clsx('text-lg font-bold', research.sentiment_score > 0.1 ? 'text-emerald-400' : research.sentiment_score < -0.1 ? 'text-red-400' : 'text-yellow-400')}>
                        {research.sentiment_label}
                      </p>
                      <p className="text-xs text-slate-600 font-mono">{research.sentiment_score.toFixed(2)}</p>
                    </div>
                    <div className="bg-slate-900 rounded-xl p-3 text-center border border-slate-800">
                      <p className="text-xs text-slate-500">Articles</p>
                      <p className="text-lg font-bold text-white">{research.article_count}</p>
                    </div>
                    <div className="bg-slate-900 rounded-xl p-3 text-center border border-slate-800">
                      <p className="text-xs text-slate-500">FII Signal</p>
                      <p className="text-lg font-bold text-slate-200">{research.fii_signal ?? '—'}</p>
                    </div>
                  </div>
                  <div className="bg-slate-900 rounded-xl p-4 border border-slate-800">
                    <p className="text-xs text-slate-500 mb-2">Sentiment Reasoning</p>
                    <p className="text-sm text-slate-200 leading-relaxed">{research.sentiment_reasoning}</p>
                  </div>
                  {research.summary && (
                    <div className="bg-slate-900 rounded-xl p-4 border border-slate-800">
                      <p className="text-xs text-slate-500 mb-2">News Summary ({research.article_count} articles)</p>
                      <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-line">{research.summary}</p>
                    </div>
                  )}
                  <div className="bg-slate-900 rounded-xl p-4 border border-slate-800">
                    <p className="text-xs text-slate-500 mb-1">RAG Filing Analysis</p>
                    <p className="text-xs text-slate-600 mb-2">From company filings stored in vector DB</p>
                    <p className="text-sm text-slate-300 leading-relaxed">{research.rag_answer}</p>
                  </div>
                </>
              ) : <p className="text-slate-400 text-sm">No research data. Run analysis first.</p>}
            </>
          )}

          {tab === 'risk' && (
            <>
              {risk ? (
                <>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-slate-900 rounded-xl p-4 border border-slate-800">
                      <p className="text-xs text-slate-500 mb-1">Decision</p>
                      <p className={clsx('text-2xl font-bold', risk.decision === 'PASS' ? 'text-emerald-400' : 'text-red-400')}>{risk.decision}</p>
                    </div>
                    <div className="bg-slate-900 rounded-xl p-4 border border-slate-800">
                      <p className="text-xs text-slate-500 mb-1">Suggested Qty</p>
                      <p className="text-2xl font-bold text-white">{risk.suggested_qty} shares</p>
                    </div>
                    <div className="bg-slate-900 rounded-xl p-4 border border-slate-800">
                      <p className="text-xs text-slate-500 mb-1">Stop Loss</p>
                      <p className="text-xl font-bold text-red-400 font-mono">₹{risk.stop_loss?.toFixed(2)}</p>
                      <p className="text-xs text-slate-600 mt-1">Cap losses here</p>
                    </div>
                    <div className="bg-slate-900 rounded-xl p-4 border border-slate-800">
                      <p className="text-xs text-slate-500 mb-1">Take Profit</p>
                      <p className="text-xl font-bold text-emerald-400 font-mono">₹{risk.take_profit?.toFixed(2)}</p>
                      <p className="text-xs text-slate-600 mt-1">Lock gains here</p>
                    </div>
                  </div>
                  <div className="bg-slate-900 rounded-xl p-4 border border-slate-800">
                    <p className="text-xs text-slate-500 mb-2">Risk Agent Reasoning</p>
                    <p className="text-sm text-slate-200">{risk.reason}</p>
                  </div>
                  <Explain title="Stop loss">Current Price − (ATR × 2). Protects against abnormal moves without cutting normal volatility.</Explain>
                  <Explain title="Take profit">Current Price + (ATR × 3). Risk:reward of 1:1.5. For every ₹1 risked, target ₹1.5 gain.</Explain>
                </>
              ) : <p className="text-slate-400 text-sm">No risk data. Run analysis first.</p>}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function TickerCard({ ticker }: { ticker: string }) {
  const qc = useQueryClient()
  const [polling, setPolling] = useState<string | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [expanded, setExpanded] = useState(false)

  const { data: signal, isLoading } = useQuery<SignalResponse>({
    queryKey: ['signal', ticker],
    queryFn: () => getSignal(ticker),
    retry: false,
    staleTime: 30_000,
  })

  useEffect(() => {
    if (!polling) return
    let done = false
    const iv = setInterval(async () => {
      try {
        const res = await getAnalysisResult(polling)
        if ('status' in res && res.status === 'completed') {
          clearInterval(iv)
          done = true
          setPolling(null)
          qc.invalidateQueries({ queryKey: ['signal', ticker] })
          const r = res as { final_signal?: string }
          toast.success(`${ticker}: ${r.final_signal ?? 'done'}`)
        }
      } catch { /* still pending */ }
    }, 3000)
    return () => { if (!done) clearInterval(iv) }
  }, [polling, ticker, qc])

  const { mutate: runAnalysis, isPending } = useMutation({
    mutationFn: () => analyzeStock(ticker, 'signal_only'),
    onSuccess: (data) => { setPolling(data.query_id); toast.loading(`Analyzing ${ticker}…`, { id: ticker }) },
    onError: () => toast.error('Analysis failed. Is Celery running?'),
  })

  const { mutate: doRemove } = useMutation({
    mutationFn: () => removeFromWatchlist(ticker),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['watchlist'] }); toast.success(`${ticker} removed`) },
  })

  const isAnalyzing = isPending || !!polling

  return (
    <>
      {showModal && signal && <SignalModal ticker={ticker} signal={signal} onClose={() => setShowModal(false)} />}
      <div className={clsx(
        'bg-slate-900 rounded-xl border transition-all duration-150 flex flex-col group',
        cardBorder(signal?.signal)
      )}>
        {/* Header */}
        <div className="flex items-center justify-between gap-2 px-4 pt-4 pb-3">
          <span className="font-bold text-white font-mono tracking-wider text-base">{ticker}</span>
          <div className="flex items-center gap-2">
            {isLoading ? <span className="text-slate-600 text-xs">—</span>
              : signal ? (
                <span className={clsx('text-xs font-semibold px-2.5 py-0.5 rounded-full', signalBadge(signal.signal))}>
                  {signal.signal}
                </span>
              ) : (
                <span className="text-slate-600 text-xs bg-slate-800 border border-slate-700/50 px-2.5 py-0.5 rounded-full">No signal</span>
              )}
            <button
              onClick={() => doRemove()}
              title="Remove"
              className="opacity-0 group-hover:opacity-100 transition-opacity text-slate-600 hover:text-red-400"
            >
              <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
        </div>

        {signal ? (
          <>
            {signal.raw_output?.quant?.current_price != null && (
              <div className="px-4 pb-2">
                <span className="text-white font-mono text-2xl font-bold">₹{signal.raw_output.quant.current_price.toFixed(2)}</span>
              </div>
            )}
            <div className="border-t border-slate-800 mx-4" />
            <div className="flex flex-wrap gap-x-4 gap-y-1 px-4 py-2.5 text-xs">
              {signal.confidence != null && (
                <span className="text-slate-500">Confidence <span className="text-slate-300 font-mono">{(signal.confidence * 100).toFixed(0)}%</span></span>
              )}
              {signal.sentiment_score != null && (
                <span className="text-slate-500">Sentiment <span className="text-slate-300 font-mono">{signal.sentiment_score.toFixed(2)}</span></span>
              )}
              {signal.raw_output?.quant?.atr_14 != null && (
                <span className="text-slate-500">ATR <span className="text-slate-300 font-mono">₹{signal.raw_output.quant.atr_14.toFixed(1)}</span></span>
              )}
            </div>
            {signal.summary && (
              <>
                <div className="border-t border-slate-800 mx-4" />
                <div className="px-4 pt-3 pb-1">
                  <p
                    className={clsx('text-xs text-slate-400 leading-relaxed cursor-pointer hover:text-slate-300', expanded ? '' : 'line-clamp-3')}
                    onClick={() => setExpanded(v => !v)}
                  >
                    {signal.summary}
                  </p>
                  <button onClick={() => setShowModal(true)} className="text-xs text-indigo-400 hover:text-indigo-300 mt-1.5 inline-block">
                    Full analysis →
                  </button>
                </div>
              </>
            )}
            <div className="border-t border-slate-800 mx-4 mt-2" />
            <div className="flex items-center justify-between gap-2 px-4 py-3">
              <button
                onClick={() => runAnalysis()}
                disabled={isAnalyzing}
                className="bg-indigo-600/80 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-600 text-white text-xs px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5"
              >
                {isAnalyzing ? (
                  <><span className="animate-spin inline-block w-3 h-3 border border-white border-t-transparent rounded-full" />Analyzing…</>
                ) : <>▶ Analyze</>}
              </button>
              {signal.generated_at && (
                <span className="text-xs text-slate-700 font-mono">{new Date(signal.generated_at).toLocaleDateString('en-IN')}</span>
              )}
            </div>
          </>
        ) : (
          <div className="px-4 pb-4 flex flex-col gap-3">
            <p className="text-xs text-slate-600">No analysis run yet</p>
            <button
              onClick={() => runAnalysis()}
              disabled={isAnalyzing}
              className="bg-indigo-600/80 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-600 text-white text-xs px-3 py-1.5 rounded-lg transition-colors self-start flex items-center gap-1.5"
            >
              {isAnalyzing ? (
                <><span className="animate-spin inline-block w-3 h-3 border border-white border-t-transparent rounded-full" />Analyzing…</>
              ) : <>▶ Run Analysis</>}
            </button>
          </div>
        )}
      </div>
    </>
  )
}

export default function WatchlistPage() {
  const qc = useQueryClient()
  const [filter, setFilter] = useState<Filter>('ALL')

  const { data: watchlist, isLoading, isError } = useQuery({
    queryKey: ['watchlist'],
    queryFn: getWatchlist,
    refetchInterval: 30_000,
  })

  const { mutate: addTicker, isPending: adding } = useMutation({
    mutationFn: ({ ticker, name }: { ticker: string; name: string }) => addToWatchlist(ticker, name),
    onSuccess: (item) => {
      qc.invalidateQueries({ queryKey: ['watchlist'] })
      toast.success(`${item.ticker} added to watchlist`)
    },
    onError: () => toast.error('Failed to add ticker'),
  })

  const [bulkAnalyzing, setBulkAnalyzing] = useState(false)
  const [bulkProgress, setBulkProgress] = useState<{ done: number; total: number } | null>(null)

  const runBulkAnalysis = async () => {
    if (!watchlist || watchlist.length === 0) return
    setBulkAnalyzing(true)
    setBulkProgress({ done: 0, total: watchlist.length })
    for (let i = 0; i < watchlist.length; i++) {
      try {
        await analyzeStock(watchlist[i].ticker, 'signal_only')
      } catch { /* continue */ }
      setBulkProgress({ done: i + 1, total: watchlist.length })
      await new Promise(r => setTimeout(r, 400))
    }
    setBulkAnalyzing(false)
    setBulkProgress(null)
    qc.invalidateQueries({ queryKey: ['signal'] })
    toast.success('Bulk analysis complete!')
  }

  const filterChips: { id: Filter; label: string }[] = [
    { id: 'ALL', label: 'All' },
    { id: 'BUY', label: 'BUY' },
    { id: 'SELL', label: 'SELL' },
    { id: 'HOLD', label: 'HOLD' },
    { id: 'NONE', label: 'No Signal' },
  ]

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Watchlist</h1>
          <p className="text-slate-500 text-sm mt-0.5">{watchlist?.length ?? 0} tickers tracked</p>
        </div>
        <div className="flex items-center gap-2">
          {bulkProgress && (
            <span className="text-xs text-slate-400">Analyzing {bulkProgress.done}/{bulkProgress.total}…</span>
          )}
          <button
            onClick={runBulkAnalysis}
            disabled={bulkAnalyzing || !watchlist?.length}
            className="text-xs px-3 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-300 rounded-lg transition-colors border border-slate-700 flex items-center gap-1.5"
          >
            {bulkAnalyzing ? (
              <><span className="animate-spin inline-block w-3 h-3 border border-slate-400 border-t-transparent rounded-full" />Analyzing all…</>
            ) : <>⚡ Analyze All</>}
          </button>
        </div>
      </div>

      <div className="flex gap-2 items-center">
        <StockSearch onSelect={(ticker, name) => { if (!adding) addTicker({ ticker, name }) }} />
        {adding && <span className="text-xs text-slate-400 flex-shrink-0">Adding…</span>}
      </div>

      {/* Signal filter chips */}
      <div className="flex items-center gap-2 flex-wrap">
        {filterChips.map(c => (
          <button
            key={c.id}
            onClick={() => setFilter(c.id)}
            className={clsx(
              'text-xs px-3 py-1.5 rounded-full font-medium transition-colors border',
              filter === c.id
                ? c.id === 'BUY' ? 'bg-emerald-600/20 text-emerald-400 border-emerald-500/30'
                  : c.id === 'SELL' ? 'bg-red-600/20 text-red-400 border-red-500/30'
                  : c.id === 'HOLD' ? 'bg-amber-600/20 text-amber-400 border-amber-500/30'
                  : 'bg-indigo-600/20 text-indigo-400 border-indigo-500/30'
                : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-slate-200'
            )}
          >
            {c.label}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => <CardSkeleton key={i} rows={3} />)}
        </div>
      )}
      {isError && <p className="text-red-400 text-sm">Failed to load watchlist.</p>}

      {watchlist && watchlist.length === 0 && (
        <div className="bg-slate-900 border border-dashed border-slate-700 rounded-xl p-10 text-center">
          <svg className="w-10 h-10 text-slate-700 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" />
          </svg>
          <p className="text-slate-400 text-sm font-medium">No tickers yet</p>
          <p className="text-slate-600 text-xs mt-1">Search above to add stocks · Try "Tata", "Reliance", "Infosys"</p>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {watchlist?.map(item => <TickerCard key={item.id} ticker={item.ticker} />)}
      </div>
    </div>
  )
}
