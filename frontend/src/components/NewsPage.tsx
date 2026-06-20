import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getNews, refreshNews, type NewsItem } from '../api/client'

function sentimentLabel(score: number | null) {
  if (score == null) return { label: 'Unknown', color: 'text-slate-400', bg: 'bg-slate-700' }
  if (score > 0.2) return { label: 'Bullish', color: 'text-emerald-400', bg: 'bg-emerald-900/50' }
  if (score < -0.2) return { label: 'Bearish', color: 'text-red-400', bg: 'bg-red-900/50' }
  return { label: 'Neutral', color: 'text-yellow-400', bg: 'bg-yellow-900/30' }
}

function SentimentBar({ score }: { score: number | null }) {
  if (score == null) return null
  const pct = ((score + 1) / 2) * 100
  const color = score > 0.2 ? 'bg-emerald-500' : score < -0.2 ? 'bg-red-500' : 'bg-yellow-500'
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-slate-500 w-4 text-right">−1</span>
      <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden relative">
        <div className="absolute inset-y-0 left-1/2 w-px bg-slate-600" />
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-slate-500 w-4">+1</span>
    </div>
  )
}

function NewsCard({ article }: { article: NewsItem }) {
  const s = sentimentLabel(article.sentiment_score)
  const pubDate = article.published_at ? new Date(article.published_at) : null

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 flex flex-col gap-3 hover:border-slate-500 transition-colors">
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          {article.ticker && (
            <span className="text-xs font-mono font-bold text-indigo-400 bg-indigo-900/40 px-2 py-0.5 rounded">{article.ticker}</span>
          )}
          {article.source && (
            <span className="text-xs text-slate-500 bg-slate-700 px-2 py-0.5 rounded">{article.source}</span>
          )}
          {pubDate && (
            <span className="text-xs text-slate-500">{pubDate.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}</span>
          )}
        </div>
        <span className={`text-xs font-medium px-2 py-0.5 rounded flex-shrink-0 ${s.bg} ${s.color}`}>{s.label}</span>
      </div>

      {/* Headline */}
      {article.url ? (
        <a href={article.url} target="_blank" rel="noopener noreferrer"
          className="text-sm text-white font-medium leading-snug hover:text-indigo-300 transition-colors">
          {article.headline}
        </a>
      ) : (
        <p className="text-sm text-white font-medium leading-snug">{article.headline}</p>
      )}

      {/* Sentiment bar */}
      {article.sentiment_score != null && (
        <div>
          <div className="flex justify-between text-xs text-slate-500 mb-1">
            <span>Sentiment Score</span>
            <span className={`font-mono font-medium ${s.color}`}>{article.sentiment_score.toFixed(2)}</span>
          </div>
          <SentimentBar score={article.sentiment_score} />
        </div>
      )}

      {/* Stock impact note */}
      {article.ticker && article.sentiment_score != null && (
        <div className={`text-xs rounded-lg px-3 py-2 ${s.bg} ${s.color} leading-relaxed`}>
          {article.sentiment_score > 0.2
            ? `This news is likely positive for ${article.ticker}. May push price upward if sentiment is confirmed by volume.`
            : article.sentiment_score < -0.2
            ? `This news is likely negative for ${article.ticker}. Watch for downside pressure or increased sell volume.`
            : `Neutral impact on ${article.ticker}. Monitor for follow-up news that could shift sentiment.`
          }
        </div>
      )}
    </div>
  )
}

export default function NewsPage() {
  const [tickerFilter, setTickerFilter] = useState('')
  const qc = useQueryClient()

  const { data: news, isLoading, isError } = useQuery({
    queryKey: ['news', tickerFilter],
    queryFn: () => getNews(tickerFilter || undefined, 100),
    staleTime: 60_000,
    refetchInterval: 120_000,
  })

  const { mutate: doRefresh, isPending: refreshing, data: refreshResult } = useMutation({
    mutationFn: refreshNews,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['news'] }),
  })

  const bullish = news?.filter(n => (n.sentiment_score ?? 0) > 0.2).length ?? 0
  const bearish = news?.filter(n => (n.sentiment_score ?? 0) < -0.2).length ?? 0
  const neutral = (news?.length ?? 0) - bullish - bearish

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-xl font-semibold text-white">Market News</h2>
          <p className="text-xs text-slate-500 mt-0.5">AI-ingested news with sentiment analysis and stock impact</p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          {news && news.length > 0 && (
            <div className="flex items-center gap-3 text-xs">
              <span className="text-emerald-400 bg-emerald-900/40 px-2 py-1 rounded">{bullish} Bullish</span>
              <span className="text-yellow-400 bg-yellow-900/30 px-2 py-1 rounded">{neutral} Neutral</span>
              <span className="text-red-400 bg-red-900/40 px-2 py-1 rounded">{bearish} Bearish</span>
            </div>
          )}
          <button
            onClick={() => doRefresh()}
            disabled={refreshing}
            className="flex items-center gap-1.5 bg-indigo-600/80 hover:bg-indigo-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-xs px-3 py-1.5 rounded-lg transition-colors"
          >
            {refreshing ? (
              <>
                <span className="animate-spin inline-block w-3 h-3 border border-white border-t-transparent rounded-full" />
                Fetching…
              </>
            ) : (
              '↻ Fetch Latest News'
            )}
          </button>
          {refreshResult && !refreshing && (
            <span className="text-xs text-emerald-400">
              +{refreshResult.ingested} articles from {refreshResult.tickers.length} tickers
            </span>
          )}
        </div>
      </div>

      {/* Filter */}
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={tickerFilter}
          onChange={e => setTickerFilter(e.target.value.toUpperCase())}
          placeholder="Filter by ticker… e.g. WIPRO.NS"
          className="bg-slate-800 border border-slate-600 focus:border-indigo-500 outline-none rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 transition-colors w-56"
        />
        {tickerFilter && (
          <button onClick={() => setTickerFilter('')} className="text-slate-400 hover:text-white text-sm">Clear</button>
        )}
      </div>

      {/* Legend */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 flex flex-col gap-2">
        <p className="text-xs font-medium text-slate-300">How to read this page</p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs text-slate-400">
          <div className="flex gap-2"><span className="text-emerald-400">●</span> <span><strong className="text-slate-300">Bullish (score &gt; 0.2):</strong> News is positive. Market sentiment favours the stock going up.</span></div>
          <div className="flex gap-2"><span className="text-yellow-400">●</span> <span><strong className="text-slate-300">Neutral (−0.2 to 0.2):</strong> Mixed or unclear news. Wait for more signals before acting.</span></div>
          <div className="flex gap-2"><span className="text-red-400">●</span> <span><strong className="text-slate-300">Bearish (score &lt; −0.2):</strong> Negative news. Could indicate downside risk for the stock.</span></div>
        </div>
        <p className="text-xs text-slate-500 mt-1">Sentiment scores are generated by Groq AI (Llama 3.3 70B) after reading each article. Sources: NewsAPI, Yahoo Finance RSS.</p>
      </div>

      {isLoading && <p className="text-slate-400 text-sm">Loading news…</p>}
      {isError && <p className="text-red-400 text-sm">Failed to load news.</p>}

      {news && news.length === 0 && (
        <div className="bg-slate-800 border border-dashed border-slate-600 rounded-xl p-10 text-center flex flex-col items-center gap-3">
          <p className="text-slate-400 text-sm">No news articles yet.</p>
          <p className="text-slate-500 text-xs">Add tickers to your watchlist, then click <strong className="text-slate-300">↻ Fetch Latest News</strong> above to pull Indian market news.</p>
          <button
            onClick={() => doRefresh()}
            disabled={refreshing}
            className="mt-1 bg-indigo-600/80 hover:bg-indigo-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-sm px-4 py-2 rounded-lg transition-colors flex items-center gap-2"
          >
            {refreshing ? (
              <>
                <span className="animate-spin inline-block w-3 h-3 border border-white border-t-transparent rounded-full" />
                Fetching news…
              </>
            ) : (
              '↻ Fetch Latest News'
            )}
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {news?.map(article => <NewsCard key={article.id} article={article} />)}
      </div>
    </div>
  )
}
