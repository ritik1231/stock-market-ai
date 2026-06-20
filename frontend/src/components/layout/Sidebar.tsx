import { NavLink } from 'react-router-dom'
import clsx from 'clsx'

const nav = [
  {
    to: '/', label: 'Dashboard', icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="w-5 h-5">
        <rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" />
      </svg>
    ),
  },
  {
    to: '/watchlist', label: 'Watchlist', icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="w-5 h-5">
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" />
      </svg>
    ),
  },
  {
    to: '/portfolio', label: 'Portfolio', icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="w-5 h-5">
        <rect x="2" y="7" width="20" height="14" rx="2" /><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" />
      </svg>
    ),
  },
  {
    to: '/trades', label: 'Trades', icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="w-5 h-5">
        <path d="M7 16V4m0 0L3 8m4-4l4 4" /><path d="M17 8v12m0 0l4-4m-4 4l-4-4" />
      </svg>
    ),
  },
  {
    to: '/news', label: 'News', icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="w-5 h-5">
        <path d="M19 20H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h10l6 6v8a2 2 0 0 1-2 2z" /><path d="M14 4v6h6" /><line x1="8" y1="13" x2="16" y2="13" /><line x1="8" y1="17" x2="12" y2="17" />
      </svg>
    ),
  },
  {
    to: '/fii-dii', label: 'FII / DII', icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="w-5 h-5">
        <line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" />
        <line x1="6" y1="20" x2="6" y2="14" /><path d="M2 20h20" />
      </svg>
    ),
  },
  {
    to: '/tax', label: 'Tax', icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="w-5 h-5">
        <rect x="2" y="3" width="20" height="18" rx="2" /><line x1="8" y1="10" x2="16" y2="10" />
        <line x1="8" y1="14" x2="16" y2="14" /><line x1="8" y1="18" x2="12" y2="18" />
        <line x1="8" y1="6" x2="16" y2="6" />
      </svg>
    ),
  },
  {
    to: '/runs', label: 'Agent Runs', icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="w-5 h-5">
        <polygon points="5 3 19 12 5 21 5 3" />
      </svg>
    ),
  },
]

export default function Sidebar() {
  return (
    <aside className="hidden md:flex flex-col fixed left-0 top-0 h-full w-56 bg-[#0d1424] border-r border-slate-800 z-30">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 py-4 border-b border-slate-800">
        <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center flex-shrink-0">
          <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={2.5} className="w-4 h-4">
            <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
            <polyline points="16 7 22 7 22 13" />
          </svg>
        </div>
        <div>
          <span className="text-white font-semibold text-sm tracking-tight leading-none block">StockAI</span>
          <span className="text-slate-500 text-xs">NSE · BSE</span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-3 overflow-y-auto">
        <p className="text-slate-600 text-xs font-medium uppercase tracking-wider px-3 mb-2">Menu</p>
        {nav.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) => clsx(
              'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-150 mb-0.5 group',
              isActive
                ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
            )}
          >
            {({ isActive }) => (
              <>
                <span className={clsx('transition-colors', isActive ? 'text-indigo-400' : 'text-slate-500 group-hover:text-slate-300')}>
                  {item.icon}
                </span>
                <span className="font-medium">{item.label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-slate-800">
        <div className="flex items-center gap-2 text-xs text-slate-600">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
          Paper Mode · No real money
        </div>
      </div>
    </aside>
  )
}
