import { useQuery } from '@tanstack/react-query'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { getPortfolio, getPortfolioHistory } from '../api/client'

function fmt(n: number, decimals = 2) {
  return n.toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

function PnlBadge({ value }: { value: number }) {
  const color = value >= 0 ? 'text-emerald-400' : 'text-red-400'
  return <span className={`font-mono font-semibold ${color}`}>{value >= 0 ? '+' : ''}₹{fmt(value)}</span>
}

export default function PortfolioPanel() {
  const { data: portfolio, isLoading, isError } = useQuery({
    queryKey: ['portfolio'],
    queryFn: getPortfolio,
    refetchInterval: 60_000,
    retry: 1,
  })

  const { data: history } = useQuery({
    queryKey: ['portfolio-history'],
    queryFn: () => getPortfolioHistory(90),
    staleTime: 60_000,
    retry: 1,
  })

  const chartData = history?.map(p => ({
    date: new Date(p.date).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' }),
    value: p.portfolio_value,
    pnl: p.daily_pnl ?? 0,
  })) ?? []

  if (isLoading) {
    return <p className="text-slate-400 text-sm">Loading portfolio…</p>
  }

  if (isError || !portfolio) {
    return (
      <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
        <p className="text-slate-400 text-sm">Portfolio data unavailable (broker not connected).</p>
      </div>
    )
  }

  const dailyPnl = history?.length
    ? (history[history.length - 1]?.daily_pnl ?? 0)
    : 0

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-xl font-semibold text-white">Portfolio</h2>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Portfolio Value', value: `₹${fmt(portfolio.portfolio_value)}` },
          { label: 'Equity', value: `₹${fmt(portfolio.equity)}` },
          { label: 'Cash', value: `₹${fmt(portfolio.cash)}` },
          { label: 'Buying Power', value: `₹${fmt(portfolio.buying_power)}` },
        ].map(({ label, value }) => (
          <div key={label} className="bg-slate-800 rounded-xl p-4 border border-slate-700">
            <p className="text-xs text-slate-400 mb-1">{label}</p>
            <p className="text-white font-semibold text-lg font-mono">{value}</p>
          </div>
        ))}
      </div>

      {/* Daily P&L badge */}
      <div className="bg-slate-800 rounded-xl px-4 py-3 border border-slate-700 text-sm flex items-center gap-2">
        <span className="text-slate-400">Today's P&L:</span>
        <PnlBadge value={dailyPnl} />
      </div>

      {/* Equity curve */}
      {chartData.length > 1 && (
        <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
          <p className="text-sm text-slate-400 mb-3">Equity Curve</p>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} width={80} tickFormatter={v => `₹${(v/1000).toFixed(0)}k`} />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid #475569', borderRadius: 8 }}
                labelStyle={{ color: '#94a3b8' }}
                formatter={(v) => typeof v === 'number' ? [`₹${fmt(v)}`, 'Value'] : [String(v), 'Value']}
              />
              <Area type="monotone" dataKey="value" stroke="#6366f1" fill="url(#equityGrad)" strokeWidth={2} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Positions table */}
      {portfolio.positions.length > 0 ? (
        <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
          <p className="text-sm text-slate-400 px-4 pt-4 pb-2">Open Positions</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-slate-400 text-xs">
                  {['Ticker', 'Qty', 'Avg Entry', 'Current', 'Market Value', 'Unrealized P&L', 'P&L %'].map(h => (
                    <th key={h} className="px-4 py-2 text-left font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {portfolio.positions.map(pos => {
                  const pnlPct = ((pos.current_price - pos.avg_entry) / pos.avg_entry) * 100
                  return (
                    <tr key={pos.ticker} className="border-b border-slate-700/50 hover:bg-slate-700/30 transition-colors">
                      <td className="px-4 py-3 font-bold text-white">{pos.ticker}</td>
                      <td className="px-4 py-3 text-slate-300 font-mono">{pos.qty}</td>
                      <td className="px-4 py-3 text-slate-300 font-mono">₹{fmt(pos.avg_entry)}</td>
                      <td className="px-4 py-3 text-slate-300 font-mono">₹{fmt(pos.current_price)}</td>
                      <td className="px-4 py-3 text-slate-300 font-mono">₹{fmt(pos.market_value)}</td>
                      <td className="px-4 py-3 font-mono"><PnlBadge value={pos.unrealized_pnl} /></td>
                      <td className={`px-4 py-3 font-mono text-xs ${pnlPct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <p className="text-slate-400 text-sm">No open positions.</p>
      )}
    </div>
  )
}
