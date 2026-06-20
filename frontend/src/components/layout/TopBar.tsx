import { useState, useEffect } from 'react'
import { NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getMarketIndices, type IndexQuote } from '../../api/client'
import clsx from 'clsx'

function useISTClock() {
  const [time, setTime] = useState('')
  const [isMarketOpen, setIsMarketOpen] = useState(false)

  useEffect(() => {
    const update = () => {
      const now = new Date()
      const ist = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }))
      const h = ist.getHours()
      const m = ist.getMinutes()
      const day = ist.getDay()

      const open = h > 9 || (h === 9 && m >= 15)
      const close = h < 15 || (h === 15 && m <= 30)
      const isWeekday = day >= 1 && day <= 5

      setIsMarketOpen(isWeekday && open && close)
      setTime(ist.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true }))
    }
    update()
    const t = setInterval(update, 1000)
    return () => clearInterval(t)
  }, [])

  return { time, isMarketOpen }
}

function IndexChip({ idx }: { idx: IndexQuote }) {
  const pos = (idx.change_pct ?? 0) >= 0
  if (!idx.price) return null
  return (
    <div className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-800/60 rounded-lg border border-slate-700/50 flex-shrink-0">
      <span className="text-slate-400 text-xs font-medium">{idx.name}</span>
      <span className="text-white text-xs font-mono font-medium">
        {idx.key === 'usdinr' ? idx.price.toFixed(2) : idx.price.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
      </span>
      {idx.change_pct != null && (
        <span className={clsx('text-xs font-mono', pos ? 'text-emerald-400' : 'text-red-400')}>
          {pos ? '+' : ''}{idx.change_pct.toFixed(2)}%
        </span>
      )}
    </div>
  )
}

const mobileNav = [
  { to: '/', label: 'Home', end: true },
  { to: '/watchlist', label: 'Watchlist' },
  { to: '/portfolio', label: 'Portfolio' },
  { to: '/news', label: 'News' },
  { to: '/runs', label: 'Runs' },
]

export default function TopBar() {
  const { time, isMarketOpen } = useISTClock()
  const { data: indices } = useQuery({
    queryKey: ['market-indices'],
    queryFn: getMarketIndices,
    refetchInterval: 60_000,
    staleTime: 30_000,
  })

  return (
    <header className="fixed top-0 left-0 right-0 md:left-56 h-14 bg-[#0a0f1e]/95 backdrop-blur border-b border-slate-800 z-20 flex items-center gap-3 px-4">
      {/* Mobile logo */}
      <div className="flex items-center gap-2 md:hidden flex-shrink-0">
        <div className="w-6 h-6 rounded-md bg-indigo-600 flex items-center justify-center">
          <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={2.5} className="w-3.5 h-3.5">
            <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
          </svg>
        </div>
        <span className="text-white font-semibold text-sm">StockAI</span>
      </div>

      {/* Index chips — scrollable */}
      <div className="flex items-center gap-2 overflow-x-auto flex-1 no-scrollbar">
        {indices?.map(idx => <IndexChip key={idx.key} idx={idx} />)}
      </div>

      {/* Market status + clock */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <div className={clsx(
          'flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-lg font-medium',
          isMarketOpen
            ? 'bg-emerald-900/40 text-emerald-400 border border-emerald-500/20'
            : 'bg-slate-800 text-slate-400 border border-slate-700/50'
        )}>
          <span className={clsx('w-1.5 h-1.5 rounded-full', isMarketOpen ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500')} />
          <span className="hidden sm:inline">{isMarketOpen ? 'NSE OPEN' : 'NSE CLOSED'}</span>
        </div>
        <span className="text-slate-500 text-xs font-mono hidden sm:inline">{time} IST</span>
      </div>

      {/* Mobile top nav */}
      <nav className="md:hidden flex items-center gap-0.5 ml-1">
        {mobileNav.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => clsx(
              'text-xs px-2 py-1.5 rounded-lg transition-colors',
              isActive ? 'text-indigo-400 bg-indigo-600/20' : 'text-slate-500 hover:text-slate-300'
            )}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </header>
  )
}
