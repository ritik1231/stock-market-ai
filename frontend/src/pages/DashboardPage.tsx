import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import clsx from 'clsx'
import {
  getWatchlist,
  getRecentRuns,
  getNews,
  getMarketIndices,
  getPortfolio,
  type IndexQuote,
} from '../api/client'
import { StatCardSkeleton, CardSkeleton } from '../components/ui/Skeleton'

function useISTMarketStatus() {
  const now = new Date()
  const ist = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }))
  const h = ist.getHours(), m = ist.getMinutes(), day = ist.getDay()
  const isWeekday = day >= 1 && day <= 5
  const afterOpen = h > 9 || (h === 9 && m >= 15)
  const beforeClose = h < 15 || (h === 15 && m <= 30)
  return isWeekday && afterOpen && beforeClose
}

function MarketBanner() {
  const isOpen = useISTMarketStatus()
  return (
    <div className={clsx(
      'rounded-xl px-4 py-3 flex items-center gap-3 border text-sm',
      isOpen
        ? 'bg-emerald-900/20 border-emerald-500/20 text-emerald-300'
        : 'bg-slate-800/60 border-slate-700/50 text-slate-400'
    )}>
      <span className={clsx('w-2 h-2 rounded-full flex-shrink-0', isOpen ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500')} />
      {isOpen
        ? 'NSE / BSE market is open — 9:15 AM to 3:30 PM IST, Monday–Friday'
        : 'NSE / BSE market is closed. Trading resumes next business day at 9:15 AM IST.'}
    </div>
  )
}

function IndexCard({ idx }: { idx: IndexQuote }) {
  const pos = (idx.change_pct ?? 0) >= 0
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 hover:border-slate-700 transition-colors">
      <p className="text-slate-500 text-xs font-medium mb-1">{idx.name}</p>
      {idx.price ? (
        <>
          <p className="text-white font-bold text-xl font-mono">
            {idx.key === 'usdinr'
              ? `₹${idx.price.toFixed(2)}`
              : idx.price.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
          </p>
          {idx.change_pct != null && (
            <p className={clsx('text-sm font-mono mt-0.5', pos ? 'text-emerald-400' : 'text-red-400')}>
              {pos ? '+' : ''}{idx.change_pct.toFixed(2)}%
              {idx.change != null && (
                <span className="ml-1.5 text-xs opacity-70">
                  ({pos ? '+' : ''}{idx.key === 'usdinr' ? idx.change.toFixed(4) : idx.change.toFixed(2)})
                </span>
              )}
            </p>
          )}
        </>
      ) : (
        <p className="text-slate-600 text-sm mt-1">Unavailable</p>
      )}
    </div>
  )
}

function SentimentDot({ score }: { score: number | null }) {
  if (score == null) return <span className="w-2 h-2 rounded-full bg-slate-600 flex-shrink-0" />
  if (score > 0.2) return <span className="w-2 h-2 rounded-full bg-emerald-500 flex-shrink-0" />
  if (score < -0.2) return <span className="w-2 h-2 rounded-full bg-red-500 flex-shrink-0" />
  return <span className="w-2 h-2 rounded-full bg-yellow-500 flex-shrink-0" />
}

export default function DashboardPage() {
  const { data: indices, isLoading: loadingIdx } = useQuery({
    queryKey: ['market-indices'],
    queryFn: getMarketIndices,
    refetchInterval: 60_000,
    staleTime: 30_000,
  })

  const { data: watchlist } = useQuery({
    queryKey: ['watchlist'],
    queryFn: getWatchlist,
    staleTime: 30_000,
  })

  const { data: runs } = useQuery({
    queryKey: ['runs'],
    queryFn: () => getRecentRuns(5),
    staleTime: 30_000,
    refetchInterval: 15_000,
  })

  const { data: news } = useQuery({
    queryKey: ['news', ''],
    queryFn: () => getNews(undefined, 4),
    staleTime: 60_000,
  })

  const { data: portfolio } = useQuery({
    queryKey: ['portfolio'],
    queryFn: getPortfolio,
    staleTime: 60_000,
    retry: false,
  })

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-slate-500 text-sm mt-0.5">AI-powered Indian market intelligence</p>
      </div>

      <MarketBanner />

      {/* Market Indices */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wider">Market Overview</h2>
          <span className="text-xs text-slate-600">Updates every 60s</span>
        </div>
        {loadingIdx ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {Array.from({ length: 5 }).map((_, i) => <StatCardSkeleton key={i} />)}
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {indices?.map(idx => <IndexCard key={idx.key} idx={idx} />)}
          </div>
        )}
      </section>

      {/* Summary Stats */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-slate-500 text-xs mb-1">Watchlist Tickers</p>
          <p className="text-white font-bold text-2xl">{watchlist?.length ?? '—'}</p>
          <Link to="/watchlist" className="text-xs text-indigo-400 hover:text-indigo-300 mt-1 inline-block">Manage →</Link>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-slate-500 text-xs mb-1">Agent Runs Today</p>
          <p className="text-white font-bold text-2xl">{runs?.length ?? '—'}</p>
          <Link to="/runs" className="text-xs text-indigo-400 hover:text-indigo-300 mt-1 inline-block">View all →</Link>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-slate-500 text-xs mb-1">Portfolio Value</p>
          <p className="text-white font-bold text-2xl font-mono">
            {portfolio ? `₹${(portfolio.portfolio_value / 1000).toFixed(0)}k` : '—'}
          </p>
          <Link to="/portfolio" className="text-xs text-indigo-400 hover:text-indigo-300 mt-1 inline-block">View →</Link>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-slate-500 text-xs mb-1">News Articles</p>
          <p className="text-white font-bold text-2xl">{news?.length ?? '—'}</p>
          <Link to="/news" className="text-xs text-indigo-400 hover:text-indigo-300 mt-1 inline-block">Read →</Link>
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Recent Agent Runs */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wider">Recent Agent Runs</h2>
            <Link to="/runs" className="text-xs text-indigo-400 hover:text-indigo-300">View all →</Link>
          </div>
          {!runs ? <CardSkeleton rows={4} /> : (
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
              {runs.length === 0 ? (
                <div className="p-6 text-center">
                  <p className="text-slate-500 text-sm">No analysis runs yet.</p>
                  <Link to="/watchlist" className="text-xs text-indigo-400 hover:text-indigo-300 mt-1 inline-block">
                    Go to Watchlist to run analysis →
                  </Link>
                </div>
              ) : (
                runs.map((run, i) => {
                  const statusColor = run.latest_status === 'success' ? 'bg-emerald-500'
                    : run.latest_status === 'error' ? 'bg-red-500'
                    : 'bg-yellow-400 animate-pulse'
                  return (
                    <div key={run.query_id} className={clsx(
                      'flex items-center gap-3 px-4 py-3 hover:bg-slate-800/50 transition-colors',
                      i < runs.length - 1 ? 'border-b border-slate-800' : ''
                    )}>
                      <span className={clsx('w-2 h-2 rounded-full flex-shrink-0', statusColor)} />
                      <div className="flex-1 min-w-0">
                        <p className="text-white text-sm font-medium truncate">{run.tickers.join(', ') || 'unknown'}</p>
                        <p className="text-slate-500 text-xs">{run.started_at ? new Date(run.started_at).toLocaleString('en-IN') : '—'}</p>
                      </div>
                      <span className="text-xs text-slate-600">{run.agent_count} agents</span>
                    </div>
                  )
                })
              )}
            </div>
          )}
        </section>

        {/* Top News */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wider">Latest News</h2>
            <Link to="/news" className="text-xs text-indigo-400 hover:text-indigo-300">View all →</Link>
          </div>
          {!news ? <CardSkeleton rows={4} /> : (
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
              {news.length === 0 ? (
                <div className="p-6 text-center">
                  <p className="text-slate-500 text-sm">No news yet.</p>
                  <Link to="/news" className="text-xs text-indigo-400 hover:text-indigo-300 mt-1 inline-block">
                    Fetch latest news →
                  </Link>
                </div>
              ) : (
                news.map((article, i) => (
                  <div key={article.id} className={clsx(
                    'flex items-start gap-3 px-4 py-3 hover:bg-slate-800/50 transition-colors',
                    i < news.length - 1 ? 'border-b border-slate-800' : ''
                  )}>
                    <SentimentDot score={article.sentiment_score} />
                    <div className="flex-1 min-w-0">
                      {article.url ? (
                        <a href={article.url} target="_blank" rel="noopener noreferrer"
                          className="text-sm text-white font-medium leading-snug hover:text-indigo-300 transition-colors line-clamp-2 block">
                          {article.headline}
                        </a>
                      ) : (
                        <p className="text-sm text-white font-medium leading-snug line-clamp-2">{article.headline}</p>
                      )}
                      <div className="flex items-center gap-2 mt-1">
                        {article.ticker && (
                          <span className="text-xs font-mono text-indigo-400">{article.ticker}</span>
                        )}
                        {article.source && (
                          <span className="text-xs text-slate-600">{article.source}</span>
                        )}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </section>
      </div>

      {/* Quick Actions */}
      <section>
        <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-3">Quick Actions</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { to: '/watchlist', label: 'Analyze Stocks', desc: 'Run AI analysis on watchlist', color: 'indigo' },
            { to: '/trades', label: 'Place Trade', desc: 'Paper trade any NSE stock', color: 'emerald' },
            { to: '/news', label: 'Fetch News', desc: 'Get latest market news', color: 'blue' },
            { to: '/fii-dii', label: 'FII/DII Flow', desc: 'Track institutional money', color: 'purple' },
          ].map(a => (
            <Link
              key={a.to}
              to={a.to}
              className="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl p-4 transition-all hover:-translate-y-0.5 hover:shadow-lg"
            >
              <p className="text-white font-medium text-sm mb-0.5">{a.label}</p>
              <p className="text-slate-500 text-xs">{a.desc}</p>
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}
