import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getTrades, placeTrade, type TradeRecord } from '../api/client'
import StockSearch from './StockSearch'

const actionColor = (a: string) => {
  if (a === 'BUY') return 'text-emerald-400'
  if (a === 'SELL') return 'text-red-400'
  return 'text-slate-400'
}

const statusBadge = (s: string) => {
  if (s === 'filled') return 'bg-emerald-900 text-emerald-300'
  if (s === 'rejected' || s === 'error') return 'bg-red-900 text-red-300'
  if (s === 'pending' || s === 'accepted') return 'bg-yellow-900 text-yellow-300'
  return 'bg-slate-700 text-slate-300'
}

function TradeForm({ onDone }: { onDone: () => void }) {
  const [ticker, setTicker] = useState('')
  const [action, setAction] = useState<'BUY' | 'SELL'>('BUY')
  const [qty, setQty] = useState('1')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const { mutate, isPending } = useMutation({
    mutationFn: () => placeTrade({ ticker: ticker.trim().toUpperCase(), action, qty: Number(qty) }),
    onSuccess: (data) => {
      setSuccess(`Order placed — ID: ${data.order_id} · Status: ${data.status}`)
      setTicker('')
      setQty('1')
      onDone()
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Trade failed'
      setError(msg)
    },
  })

  const submit = () => {
    setError(null)
    setSuccess(null)
    if (!ticker.trim()) return setError('Enter a ticker symbol')
    if (isNaN(Number(qty)) || Number(qty) <= 0) return setError('Quantity must be a positive number')
    mutate()
  }

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 flex flex-col gap-4">
      <h3 className="text-sm font-semibold text-white">Place Paper Trade</h3>

      <div className="flex flex-col gap-1">
        <label className="text-xs text-slate-400">Ticker</label>
        {ticker ? (
          <div className="flex items-center gap-2 bg-slate-900 border border-indigo-500 rounded-lg px-3 py-2">
            <span className="text-white font-mono text-sm flex-1">{ticker}</span>
            <button onClick={() => setTicker('')} className="text-slate-400 hover:text-white text-xs">Change</button>
          </div>
        ) : (
          <StockSearch
            onSelect={(t) => setTicker(t)}
            placeholder="Search stock to trade…"
          />
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400">Action</label>
          <div className="flex rounded-lg overflow-hidden border border-slate-600">
            {(['BUY', 'SELL'] as const).map(a => (
              <button
                key={a}
                onClick={() => setAction(a)}
                className={`flex-1 py-2 text-sm font-medium transition-colors ${
                  action === a
                    ? a === 'BUY' ? 'bg-emerald-600 text-white' : 'bg-red-600 text-white'
                    : 'bg-slate-900 text-slate-400 hover:text-white'
                }`}
              >
                {a}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400">Quantity</label>
          <input
            type="number"
            min="1"
            value={qty}
            onChange={e => setQty(e.target.value)}
            className="bg-slate-900 border border-slate-600 focus:border-indigo-500 outline-none rounded-lg px-3 py-2 text-sm text-white transition-colors"
          />
        </div>
      </div>

      {error && <p className="text-red-400 text-xs">{error}</p>}
      {success && <p className="text-emerald-400 text-xs">{success}</p>}

      <button
        onClick={submit}
        disabled={isPending}
        className={`text-sm font-medium rounded-lg px-4 py-2 transition-colors disabled:opacity-50 ${
          action === 'BUY'
            ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
            : 'bg-red-600 hover:bg-red-500 text-white'
        }`}
      >
        {isPending ? 'Placing order…' : `Place ${action} Order`}
      </button>

      <p className="text-xs text-slate-500">Paper trading only · No real money involved</p>
    </div>
  )
}

function TradeRow({ trade }: { trade: TradeRecord }) {
  const price = trade.filled_price ?? trade.submitted_price
  return (
    <tr className="border-b border-slate-700/50 hover:bg-slate-700/20 transition-colors">
      <td className="px-4 py-3 font-bold text-white">{trade.ticker}</td>
      <td className={`px-4 py-3 font-semibold font-mono ${actionColor(trade.action)}`}>{trade.action}</td>
      <td className="px-4 py-3 text-slate-300 font-mono">{trade.qty}</td>
      <td className="px-4 py-3 text-slate-300 font-mono">
        {price != null ? `₹${price.toFixed(2)}` : '—'}
      </td>
      <td className="px-4 py-3">
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusBadge(trade.status ?? '')}`}>
          {trade.status ?? 'unknown'}
        </span>
      </td>
      <td className="px-4 py-3 text-slate-500 text-xs">
        {new Date(trade.submitted_at).toLocaleString()}
      </td>
    </tr>
  )
}

export default function TradesPanel() {
  const qc = useQueryClient()
  const [filterTicker, setFilterTicker] = useState('')

  const { data: trades, isLoading, isError } = useQuery({
    queryKey: ['trades', filterTicker],
    queryFn: () => getTrades(filterTicker || undefined, 50),
    refetchInterval: 30_000,
  })

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-white">Trades</h2>
        <span className="text-xs text-slate-500">{trades?.length ?? 0} records</span>
      </div>

      <TradeForm onDone={() => qc.invalidateQueries({ queryKey: ['trades'] })} />

      {/* Filter */}
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={filterTicker}
          onChange={e => setFilterTicker(e.target.value.toUpperCase())}
          placeholder="Filter by ticker…"
          className="bg-slate-800 border border-slate-600 focus:border-indigo-500 outline-none rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 transition-colors w-48"
        />
        {filterTicker && (
          <button onClick={() => setFilterTicker('')} className="text-slate-400 hover:text-white text-sm">
            Clear
          </button>
        )}
      </div>

      {isLoading && <p className="text-slate-400 text-sm">Loading trades…</p>}
      {isError && <p className="text-red-400 text-sm">Failed to load trades.</p>}

      {trades && trades.length === 0 && (
        <div className="bg-slate-800 border border-dashed border-slate-600 rounded-xl p-8 text-center">
          <p className="text-slate-400 text-sm">No trades yet. Place one above.</p>
        </div>
      )}

      {trades && trades.length > 0 && (
        <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-slate-400 text-xs">
                  {['Ticker', 'Action', 'Qty', 'Fill Price', 'Status', 'Submitted'].map(h => (
                    <th key={h} className="px-4 py-3 text-left font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {trades.map(trade => <TradeRow key={trade.id} trade={trade} />)}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
