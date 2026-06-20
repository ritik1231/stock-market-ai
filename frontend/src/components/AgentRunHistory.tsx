import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getRecentRuns, getQueryLogs, type AgentLogDetail, type RunSummary } from '../api/client'

const AGENT_ORDER = ['research_agent', 'quant_agent', 'risk_agent', 'execution_agent', 'orchestrator']

const statusIcon = (s: string) => {
  if (s === 'success') return <span className="text-emerald-400 text-base">✓</span>
  if (s === 'error' || s === 'dead_letter') return <span className="text-red-400 text-base">✗</span>
  if (s === 'started') return <span className="text-yellow-400 text-base">⟳</span>
  return <span className="text-slate-500 text-base">○</span>
}

const statusDot = (s: string) => {
  if (s === 'success') return 'bg-emerald-400'
  if (s === 'error') return 'bg-red-400'
  if (s === 'started') return 'bg-yellow-400 animate-pulse'
  return 'bg-slate-500'
}

function JsonAccordion({ label, data }: { label: string; data: Record<string, unknown> | null }) {
  const [open, setOpen] = useState(false)
  if (!data) return null
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(v => !v)}
        className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
      >
        {open ? '▾' : '▸'} {label}
      </button>
      {open && (
        <pre className="mt-1 text-xs bg-slate-900 rounded-lg p-3 overflow-auto max-h-48 text-slate-300 border border-slate-700">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  )
}

function AgentTimeline({ queryId }: { queryId: string }) {
  const { data: logs, isLoading } = useQuery<AgentLogDetail[]>({
    queryKey: ['query-logs', queryId],
    queryFn: () => getQueryLogs(queryId),
    staleTime: 30_000,
  })

  if (isLoading) return <p className="text-slate-400 text-xs mt-2">Loading logs…</p>

  if (!logs || logs.length === 0) return <p className="text-slate-400 text-xs mt-2">No logs found.</p>

  const sorted = [...logs].sort((a, b) => {
    const ai = AGENT_ORDER.indexOf(a.agent_name)
    const bi = AGENT_ORDER.indexOf(b.agent_name)
    if (ai !== bi) return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi)
    return (a.started_at ?? '') < (b.started_at ?? '') ? -1 : 1
  })

  const maxLatency = Math.max(...sorted.map(l => l.latency_ms ?? 0), 1)

  return (
    <div className="flex flex-col gap-3 mt-3">
      {sorted.map((log) => (
        <div key={log.id} className="bg-slate-900 rounded-lg p-3 border border-slate-700">
          <div className="flex items-center gap-2 mb-1">
            {statusIcon(log.status)}
            <span className="text-sm font-medium text-white">{log.agent_name}</span>
            <span className="ml-auto text-xs text-slate-500">{log.latency_ms != null ? `${log.latency_ms}ms` : '—'}</span>
          </div>

          {log.latency_ms != null && (
            <div className="h-1 rounded-full bg-slate-700 mt-1 mb-2">
              <div
                className="h-1 rounded-full bg-indigo-500"
                style={{ width: `${(log.latency_ms / maxLatency) * 100}%` }}
              />
            </div>
          )}

          {log.error_message && (
            <p className="text-xs text-red-400 mt-1 font-mono">{log.error_message}</p>
          )}

          <JsonAccordion label="Input" data={log.task_input} />
          <JsonAccordion label="Output" data={log.task_output} />
        </div>
      ))}
    </div>
  )
}

function RunRow({ run, selected, onSelect }: {
  run: RunSummary
  selected: boolean
  onSelect: () => void
}) {
  const ts = run.started_at ? new Date(run.started_at).toLocaleString() : '—'
  return (
    <button
      onClick={onSelect}
      className={`w-full text-left px-3 py-2 rounded-lg transition-colors text-sm ${
        selected ? 'bg-indigo-600 text-white' : 'hover:bg-slate-700 text-slate-300'
      }`}
    >
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${statusDot(run.latest_status)}`} />
        <span className="font-medium truncate">{run.tickers.join(', ') || 'unknown'}</span>
        <span className="ml-auto text-xs text-slate-500 flex-shrink-0">{run.agent_count} agents</span>
      </div>
      <p className="text-xs text-slate-500 mt-0.5 ml-4">{ts}</p>
    </button>
  )
}

export default function AgentRunHistory() {
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { data: runs, isLoading } = useQuery<RunSummary[]>({
    queryKey: ['runs'],
    queryFn: () => getRecentRuns(50),
    refetchInterval: 15_000,
  })

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-xl font-semibold text-white">Agent Run History</h2>

      <div className="flex gap-4 h-[600px]">
        {/* Sidebar */}
        <div className="w-64 flex-shrink-0 bg-slate-800 rounded-xl border border-slate-700 overflow-y-auto p-2">
          {isLoading && <p className="text-slate-400 text-xs p-2">Loading runs…</p>}
          {runs?.length === 0 && <p className="text-slate-400 text-xs p-2">No runs yet.</p>}
          {runs?.map(run => (
            <RunRow
              key={run.query_id}
              run={run}
              selected={selectedId === run.query_id}
              onSelect={() => setSelectedId(run.query_id)}
            />
          ))}
        </div>

        {/* Detail pane */}
        <div className="flex-1 bg-slate-800 rounded-xl border border-slate-700 overflow-y-auto p-4">
          {!selectedId ? (
            <p className="text-slate-400 text-sm">Select a run from the sidebar to view its agent trace.</p>
          ) : (
            <>
              <p className="text-xs text-slate-500 font-mono break-all">{selectedId}</p>
              <AgentTimeline queryId={selectedId} />
            </>
          )}
        </div>
      </div>
    </div>
  )
}
