export function SkeletonBox({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse bg-slate-800 rounded-lg ${className}`} />
}

export function SkeletonText({ lines = 1, className = '' }: { lines?: number; className?: string }) {
  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="animate-pulse bg-slate-800 rounded h-3"
          style={{ width: i === lines - 1 && lines > 1 ? '65%' : '100%' }}
        />
      ))}
    </div>
  )
}

export function StatCardSkeleton() {
  return (
    <div className="bg-slate-900 rounded-xl p-4 border border-slate-800 animate-pulse">
      <div className="h-3 w-20 bg-slate-800 rounded mb-3" />
      <div className="h-7 w-28 bg-slate-800 rounded" />
    </div>
  )
}

export function CardSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="bg-slate-900 rounded-xl border border-slate-800 p-4 flex flex-col gap-3 animate-pulse">
      <div className="h-4 w-32 bg-slate-800 rounded" />
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-3 bg-slate-800 rounded" style={{ width: `${70 + (i * 10) % 30}%` }} />
      ))}
    </div>
  )
}
