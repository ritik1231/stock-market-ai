import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { searchStocks, type SearchResult } from '../api/client'

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return debounced
}

interface Props {
  onSelect: (ticker: string, name: string) => void
  placeholder?: string
}

export default function StockSearch({ onSelect, placeholder = 'Search stocks… e.g. Tata, Reliance, INFY' }: Props) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const debouncedQuery = useDebounce(query, 300)
  const containerRef = useRef<HTMLDivElement>(null)

  const { data: results, isFetching } = useQuery<SearchResult[]>({
    queryKey: ['search', debouncedQuery],
    queryFn: () => searchStocks(debouncedQuery),
    enabled: debouncedQuery.length >= 2,
    staleTime: 30_000,
  })

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleSelect = (result: SearchResult) => {
    onSelect(result.ticker, result.name)
    setQuery('')
    setOpen(false)
  }

  return (
    <div ref={containerRef} className="relative flex-1">
      <div className="flex items-center bg-slate-800 border border-slate-600 focus-within:border-indigo-500 rounded-lg transition-colors">
        <svg className="w-4 h-4 text-slate-400 ml-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          type="text"
          value={query}
          onChange={e => { setQuery(e.target.value); setOpen(true) }}
          onFocus={() => query.length >= 2 && setOpen(true)}
          placeholder={placeholder}
          className="flex-1 bg-transparent outline-none px-3 py-2 text-sm text-white placeholder-slate-500"
        />
        {isFetching && (
          <span className="mr-3 animate-spin inline-block w-3 h-3 border border-slate-400 border-t-transparent rounded-full flex-shrink-0" />
        )}
      </div>

      {open && results && results.length > 0 && (
        <div className="absolute top-full mt-1 left-0 right-0 bg-slate-800 border border-slate-600 rounded-lg shadow-xl z-20 overflow-hidden max-h-64 overflow-y-auto">
          {results.map(r => (
            <button
              key={r.ticker}
              onClick={() => handleSelect(r)}
              className="w-full text-left px-4 py-2.5 hover:bg-slate-700 transition-colors flex items-center justify-between gap-3 border-b border-slate-700/50 last:border-0"
            >
              <div className="flex flex-col min-w-0">
                <span className="text-white font-medium text-sm font-mono">{r.ticker}</span>
                <span className="text-slate-400 text-xs truncate">{r.name}</span>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <span className="text-xs text-slate-500">{r.exchange}</span>
                <span className="text-xs bg-slate-700 text-slate-400 px-1.5 py-0.5 rounded">{r.type}</span>
              </div>
            </button>
          ))}
        </div>
      )}

      {open && debouncedQuery.length >= 2 && !isFetching && results?.length === 0 && (
        <div className="absolute top-full mt-1 left-0 right-0 bg-slate-800 border border-slate-600 rounded-lg shadow-xl z-20 px-4 py-3">
          <p className="text-slate-400 text-sm">No results for "{debouncedQuery}"</p>
        </div>
      )}
    </div>
  )
}
