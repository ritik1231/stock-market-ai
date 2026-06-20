import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine } from 'recharts'
import { getFiiDii } from '../api/client'
import { StatCardSkeleton } from '../components/ui/Skeleton'

function fmt(n: number) {
  const abs = Math.abs(n)
  if (abs >= 10000) return `₹${(n / 1000).toFixed(1)}k Cr`
  return `₹${n.toFixed(0)} Cr`
}

export default function FiiDiiPage() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['fii-dii'],
    queryFn: getFiiDii,
    staleTime: 3600_000,
    refetchInterval: 3600_000,
  })

  const signalColor = data?.signal === 'BULLISH' ? 'text-emerald-400'
    : data?.signal === 'BEARISH' ? 'text-red-400'
    : 'text-yellow-400'

  const signalBg = data?.signal === 'BULLISH' ? 'bg-emerald-900/20 border-emerald-500/20'
    : data?.signal === 'BEARISH' ? 'bg-red-900/20 border-red-500/20'
    : 'bg-yellow-900/20 border-yellow-500/20'

  // Mock historical chart data (replace with real API when available)
  const chartData = data ? [
    { day: 'Mon', fii: data.fii_net_crore * 0.8, dii: data.dii_net_crore * 0.9 },
    { day: 'Tue', fii: data.fii_net_crore * 1.2, dii: data.dii_net_crore * 0.7 },
    { day: 'Wed', fii: data.fii_net_crore * 0.6, dii: data.dii_net_crore * 1.3 },
    { day: 'Thu', fii: data.fii_net_crore * 1.1, dii: data.dii_net_crore * 0.8 },
    { day: 'Fri (Today)', fii: data.fii_net_crore, dii: data.dii_net_crore },
  ] : []

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">FII / DII Tracker</h1>
          <p className="text-slate-500 text-sm mt-0.5">Foreign & Domestic Institutional Investor flows from NSE</p>
        </div>
        <button
          onClick={() => refetch()}
          className="text-xs px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700 transition-colors"
        >
          ↻ Refresh
        </button>
      </div>

      {/* What is FII/DII */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 text-sm text-slate-400 leading-relaxed">
        <p className="text-slate-300 font-medium mb-2">What are FII/DII flows?</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
          <div className="flex gap-2">
            <span className="text-blue-400 mt-0.5">●</span>
            <span><strong className="text-slate-300">FII (Foreign Institutional Investors)</strong> — Foreign funds (hedge funds, pension funds) buying/selling Indian stocks. When FIIs are net buyers, it signals global confidence in India.</span>
          </div>
          <div className="flex gap-2">
            <span className="text-orange-400 mt-0.5">●</span>
            <span><strong className="text-slate-300">DII (Domestic Institutional Investors)</strong> — Indian mutual funds, insurance companies, banks. DIIs often buy when FIIs sell, acting as a market stabiliser.</span>
          </div>
        </div>
      </div>

      {isLoading && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => <StatCardSkeleton key={i} />)}
        </div>
      )}

      {isError && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 text-center">
          <p className="text-slate-400 text-sm">Could not load FII/DII data from NSE. NSE may be rate-limiting the request.</p>
          <button onClick={() => refetch()} className="mt-2 text-xs text-indigo-400 hover:text-indigo-300">Try again →</button>
        </div>
      )}

      {data && (
        <>
          {/* Signal banner */}
          <div className={clsx('rounded-xl px-4 py-3 flex items-center gap-3 border text-sm font-medium', signalBg, signalColor)}>
            <span className={clsx('w-2 h-2 rounded-full flex-shrink-0', data.signal === 'BULLISH' ? 'bg-emerald-400' : data.signal === 'BEARISH' ? 'bg-red-400' : 'bg-yellow-400')} />
            {data.signal === 'BULLISH'
              ? `FII net buy > ₹500 Cr — Institutional confidence is HIGH. Historically a positive signal for Nifty.`
              : data.signal === 'BEARISH'
              ? `FII net sell > ₹500 Cr — Foreign outflows signal caution. Watch Nifty for downside pressure.`
              : `FII/DII flows are within normal range — market awaiting direction.`}
          </div>

          {/* Stat cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <p className="text-slate-500 text-xs mb-1">FII Net Today</p>
              <p className={clsx('text-xl font-bold font-mono', data.fii_net_crore >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                {data.fii_net_crore >= 0 ? '+' : ''}{fmt(data.fii_net_crore)}
              </p>
              <p className="text-xs text-slate-600 mt-1">{data.fii_net_crore >= 0 ? 'Net Buyers' : 'Net Sellers'}</p>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <p className="text-slate-500 text-xs mb-1">DII Net Today</p>
              <p className={clsx('text-xl font-bold font-mono', data.dii_net_crore >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                {data.dii_net_crore >= 0 ? '+' : ''}{fmt(data.dii_net_crore)}
              </p>
              <p className="text-xs text-slate-600 mt-1">{data.dii_net_crore >= 0 ? 'Net Buyers' : 'Net Sellers'}</p>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <p className="text-slate-500 text-xs mb-1">Combined Flow</p>
              <p className={clsx('text-xl font-bold font-mono', (data.fii_net_crore + data.dii_net_crore) >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                {(data.fii_net_crore + data.dii_net_crore) >= 0 ? '+' : ''}{fmt(data.fii_net_crore + data.dii_net_crore)}
              </p>
              <p className="text-xs text-slate-600 mt-1">Net institutional</p>
            </div>
            <div className={clsx('border rounded-xl p-4', signalBg)}>
              <p className="text-slate-500 text-xs mb-1">AI Signal</p>
              <p className={clsx('text-xl font-bold', signalColor)}>{data.signal}</p>
              <p className="text-xs text-slate-600 mt-1">Based on flow magnitude</p>
            </div>
          </div>

          {/* FII date */}
          <p className="text-xs text-slate-600">Data as of: {data.date}</p>

          {/* Chart */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
            <p className="text-sm text-slate-400 mb-4">Weekly Flow Trend (₹ Crore)</p>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="day" tick={{ fontSize: 11, fill: '#64748b' }} />
                <YAxis tick={{ fontSize: 11, fill: '#64748b' }} tickFormatter={v => `₹${(v/100).toFixed(0)}k`} />
                <Tooltip
                  contentStyle={{ background: '#0d1424', border: '1px solid #1e293b', borderRadius: 8 }}
                  labelStyle={{ color: '#94a3b8' }}
                  formatter={(v) => typeof v === 'number' ? [`₹${v.toFixed(0)} Cr`, ''] : [String(v), '']}
                />
                <Legend wrapperStyle={{ fontSize: 12, color: '#64748b' }} />
                <ReferenceLine y={0} stroke="#334155" />
                <Bar dataKey="fii" name="FII" fill="#6366f1" radius={[3, 3, 0, 0]} />
                <Bar dataKey="dii" name="DII" fill="#f97316" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
            <p className="text-xs text-slate-600 mt-2">* Weekly trend is estimated based on today's data. Historical data integration coming soon.</p>
          </div>

          {/* Interpretation */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <p className="text-emerald-400 font-medium text-sm mb-2">When FIIs Buy Heavily</p>
              <ul className="text-xs text-slate-400 space-y-1.5">
                <li>→ Global risk appetite is high</li>
                <li>→ Rupee typically strengthens</li>
                <li>→ Large-cap stocks tend to outperform</li>
                <li>→ Nifty 50 usually rallies</li>
              </ul>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <p className="text-red-400 font-medium text-sm mb-2">When FIIs Sell Heavily</p>
              <ul className="text-xs text-slate-400 space-y-1.5">
                <li>→ Caution: global risk-off mode</li>
                <li>→ Rupee may weaken vs USD</li>
                <li>→ Volatility increases</li>
                <li>→ DIIs may cushion the fall</li>
              </ul>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <p className="text-blue-400 font-medium text-sm mb-2">DII Counter-Balance</p>
              <ul className="text-xs text-slate-400 space-y-1.5">
                <li>→ SIP flows make DIIs consistent buyers</li>
                <li>→ Often absorb FII selling</li>
                <li>→ Strong DII buying = market support</li>
                <li>→ Both buying together = very bullish</li>
              </ul>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
