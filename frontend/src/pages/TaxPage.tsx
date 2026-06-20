import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { api, type TaxSummary } from '../api/client'
import { StatCardSkeleton } from '../components/ui/Skeleton'

const currentFY = new Date().getMonth() >= 3
  ? new Date().getFullYear()
  : new Date().getFullYear() - 1

const getTaxSummary = (year: number) =>
  api.get<TaxSummary>('/tax/summary', { params: { year } }).then(r => r.data)

function fmt(n: number) {
  return n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function TaxPage() {
  const [fy, setFy] = useState(currentFY)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['tax-summary', fy],
    queryFn: () => getTaxSummary(fy),
    staleTime: 300_000,
  })

  const fyLabel = `FY ${fy}–${(fy + 1).toString().slice(2)}`

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Tax Calculator</h1>
          <p className="text-slate-500 text-sm mt-0.5">Indian capital gains tax estimate (STCG / LTCG)</p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-500">Financial Year:</label>
          <select
            value={fy}
            onChange={e => setFy(Number(e.target.value))}
            className="bg-slate-900 border border-slate-700 text-white text-sm rounded-lg px-3 py-1.5 outline-none focus:border-indigo-500"
          >
            {[currentFY - 1, currentFY, currentFY + 1].map(y => (
              <option key={y} value={y}>FY {y}–{(y + 1).toString().slice(2)}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Disclaimer */}
      <div className="bg-amber-900/20 border border-amber-500/20 rounded-xl px-4 py-3 text-xs text-amber-300/80">
        ⚠ This is an estimate for paper trades only. Consult a CA or tax professional for your actual tax liability. Indian tax law may change each budget.
      </div>

      {/* Tax rules */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
        <p className="text-slate-300 font-medium text-sm mb-3">Indian Capital Gains Tax Rules (FY 2024–25 onwards)</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div className="border border-slate-800 rounded-lg p-3">
            <p className="text-yellow-400 font-medium mb-1.5">Short Term Capital Gain (STCG)</p>
            <ul className="text-slate-400 space-y-1">
              <li>→ Stock held <strong className="text-slate-300">&lt; 12 months</strong></li>
              <li>→ Tax rate: <strong className="text-emerald-400">20%</strong> (raised from 15% in Budget 2024)</li>
              <li>→ No basic exemption limit applies</li>
              <li>→ Applies to equity shares & equity MFs listed on recognised exchange</li>
            </ul>
          </div>
          <div className="border border-slate-800 rounded-lg p-3">
            <p className="text-indigo-400 font-medium mb-1.5">Long Term Capital Gain (LTCG)</p>
            <ul className="text-slate-400 space-y-1">
              <li>→ Stock held <strong className="text-slate-300">≥ 12 months</strong></li>
              <li>→ Tax rate: <strong className="text-emerald-400">12.5%</strong> (raised from 10% in Budget 2024)</li>
              <li>→ Exempt up to <strong className="text-slate-300">₹1.25 lakh</strong> per year</li>
              <li>→ No indexation benefit for equity</li>
            </ul>
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
          <p className="text-slate-400 text-sm">No closed trades for {fyLabel}.</p>
          <p className="text-slate-600 text-xs mt-1">Tax summary is computed from completed trades in your paper portfolio.</p>
        </div>
      )}

      {data && (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <p className="text-slate-500 text-xs mb-1">STCG Profit</p>
              <p className="text-white font-bold text-lg font-mono text-emerald-400">₹{fmt(data.stcg_profit)}</p>
              <p className="text-xs text-slate-600 mt-1">Tax @ 20%</p>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <p className="text-slate-500 text-xs mb-1">LTCG Profit</p>
              <p className="text-white font-bold text-lg font-mono text-indigo-400">₹{fmt(data.ltcg_profit)}</p>
              <p className="text-xs text-slate-600 mt-1">Tax @ 12.5% (above ₹1.25L)</p>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <p className="text-slate-500 text-xs mb-1">Loss Set-off</p>
              <p className="text-red-400 font-bold text-lg font-mono">−₹{fmt(data.stcg_loss + data.ltcg_loss)}</p>
              <p className="text-xs text-slate-600 mt-1">Reduces taxable gain</p>
            </div>
            <div className="bg-slate-900 border border-amber-500/20 rounded-xl p-4">
              <p className="text-slate-500 text-xs mb-1">Estimated Tax</p>
              <p className="text-amber-400 font-bold text-2xl font-mono">₹{fmt(data.total_tax)}</p>
              <p className="text-xs text-slate-600 mt-1">{fyLabel}</p>
            </div>
          </div>

          {/* Trade breakdown */}
          {data.trades && data.trades.length > 0 && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
              <p className="text-sm text-slate-400 px-4 pt-4 pb-2 font-medium">Trade Breakdown</p>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-500">
                      {['Ticker', 'Buy Date', 'Sell Date', 'Days', 'Qty', 'Buy ₹', 'Sell ₹', 'Gain', 'Type', 'Tax Est.'].map(h => (
                        <th key={h} className="px-3 py-2.5 text-left font-medium">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.trades.map((t, i) => (
                      <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                        <td className="px-3 py-2.5 font-bold text-white font-mono">{t.ticker}</td>
                        <td className="px-3 py-2.5 text-slate-400">{t.buy_date ? new Date(t.buy_date).toLocaleDateString('en-IN') : '—'}</td>
                        <td className="px-3 py-2.5 text-slate-400">{t.sell_date ? new Date(t.sell_date).toLocaleDateString('en-IN') : '—'}</td>
                        <td className="px-3 py-2.5 text-slate-400 font-mono">{t.days_held ?? '—'}</td>
                        <td className="px-3 py-2.5 text-slate-300 font-mono">{t.qty}</td>
                        <td className="px-3 py-2.5 text-slate-300 font-mono">{t.buy_price != null ? `₹${fmt(t.buy_price)}` : '—'}</td>
                        <td className="px-3 py-2.5 text-slate-300 font-mono">{t.sell_price != null ? `₹${fmt(t.sell_price)}` : '—'}</td>
                        <td className={clsx('px-3 py-2.5 font-mono font-medium', (t.gain ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                          {t.gain != null ? `${t.gain >= 0 ? '+' : ''}₹${fmt(t.gain)}` : '—'}
                        </td>
                        <td className="px-3 py-2.5">
                          <span className={clsx(
                            'px-1.5 py-0.5 rounded text-xs font-medium',
                            t.gain_type === 'STCG' ? 'bg-yellow-900/40 text-yellow-400' : t.gain_type === 'LTCG' ? 'bg-indigo-900/40 text-indigo-400' : 'bg-slate-800 text-slate-500'
                          )}>
                            {t.gain_type ?? '—'}
                          </span>
                        </td>
                        <td className="px-3 py-2.5 text-amber-400 font-mono">{t.tax_estimate != null ? `₹${fmt(t.tax_estimate)}` : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
