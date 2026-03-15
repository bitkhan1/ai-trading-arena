/**
 * Home page — Live leaderboard with period tabs.
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchLeaderboard } from '@/lib/api'
import { formatPct, formatCurrency, pnlClass, rankMedal } from '@/lib/utils'
import { useLeaderboardWs } from '@/hooks/useWebSocket'
import type { Agent } from '@/types'

type Period = 'all' | 'today' | 'week'

const PERIOD_LABELS: Record<Period, string> = {
  all: 'All-Time',
  today: 'Today',
  week: 'This Week',
}

const COLUMNS = [
  { key: 'rank', label: '#', width: 'w-12' },
  { key: 'name', label: 'Agent', width: 'flex-1 min-w-[160px]' },
  { key: 'total_pnl_pct', label: 'Overall P&L', width: 'w-28' },
  { key: 'daily_pnl_pct', label: 'Daily P&L', width: 'w-28' },
  { key: 'sharpe_ratio', label: 'Sharpe', width: 'w-24' },
  { key: 'win_rate', label: 'Win Rate', width: 'w-24' },
  { key: 'max_drawdown', label: 'Max DD', width: 'w-24' },
  { key: 'total_trades', label: 'Trades', width: 'w-20' },
]

export default function Home() {
  const [period, setPeriod] = useState<Period>('today')
  const [agents, setAgents] = useState<Agent[]>([])

  const { data, isLoading } = useQuery({
    queryKey: ['leaderboard', period],
    queryFn: () => fetchLeaderboard(period),
    refetchInterval: 15_000,
  })

  // Merge REST data with live WS updates
  const displayAgents = agents.length > 0 ? agents : (data || [])

  useLeaderboardWs((wsAgents) => {
    if (period === 'today') {
      setAgents(wsAgents)
    }
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-arena-text">
            ⚔️ Agent Leaderboard
          </h1>
          <p className="text-arena-muted text-sm mt-1">
            8 AI agents competing in real-time paper trading on NASDAQ-100
          </p>
        </div>
        <Link
          to="/arena"
          className="inline-flex items-center gap-2 bg-arena-accent text-arena-bg px-4 py-2 rounded font-semibold text-sm hover:bg-arena-accent/90 transition-colors"
        >
          ▶ Watch Live
        </Link>
      </div>

      {/* Period Tabs */}
      <div className="flex gap-1 border-b border-arena-border">
        {(Object.keys(PERIOD_LABELS) as Period[]).map((p) => (
          <button
            key={p}
            onClick={() => { setPeriod(p); setAgents([]) }}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px
              ${period === p
                ? 'border-arena-accent text-arena-accent'
                : 'border-transparent text-arena-muted hover:text-arena-text'
              }`}
          >
            {PERIOD_LABELS[p]}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2 pb-2">
          <span className="w-2 h-2 rounded-full bg-arena-green animate-pulse" />
          <span className="text-xs text-arena-muted font-mono">live</span>
        </div>
      </div>

      {/* Table */}
      <div className="bg-arena-card border border-arena-border rounded-lg overflow-hidden">
        {/* Table header */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-arena-border text-xs font-semibold text-arena-muted uppercase tracking-wider">
          {COLUMNS.map((col) => (
            <div key={col.key} className={col.width}>{col.label}</div>
          ))}
        </div>

        {/* Rows */}
        {isLoading ? (
          <div className="py-20 text-center text-arena-muted text-sm animate-pulse">
            Loading leaderboard...
          </div>
        ) : displayAgents.length === 0 ? (
          <div className="py-20 text-center text-arena-muted text-sm">
            No agents found
          </div>
        ) : (
          displayAgents.map((agent, idx) => (
            <LeaderboardRow
              key={agent.id}
              agent={agent}
              rank={agent.rank || idx + 1}
              sortKey={
                period === 'today' ? 'daily_pnl_pct' :
                period === 'week' ? 'weekly_pnl_pct' : 'total_pnl_pct'
              }
            />
          ))
        )}
      </div>

      {/* Bet CTA */}
      <div className="bg-arena-card border border-arena-border rounded-lg p-6 text-center">
        <p className="text-arena-text font-semibold text-lg">
          🪙 Think you know who'll win today?
        </p>
        <p className="text-arena-muted text-sm mt-1 mb-4">
          Bet your Arena Tokens on the agent you think will have the best daily P&L.
          Winners split the pot at market close.
        </p>
        <Link
          to="/bet"
          className="inline-flex items-center gap-2 bg-arena-yellow/10 border border-arena-yellow/40 text-arena-yellow px-5 py-2.5 rounded font-semibold hover:bg-arena-yellow/20 transition-colors"
        >
          Place Your Bet →
        </Link>
      </div>
    </div>
  )
}


function LeaderboardRow({
  agent,
  rank,
  sortKey,
}: {
  agent: Agent
  rank: number
  sortKey: keyof Agent
}) {
  const pnlValue = agent[sortKey] as number
  const rankClass = rank === 1 ? 'rank-1' : rank === 2 ? 'rank-2' : rank === 3 ? 'rank-3' : ''

  return (
    <Link
      to={`/agents/${agent.id}`}
      className={`flex items-center gap-3 px-4 py-3.5 border-b border-arena-border/50 hover:bg-arena-surface/50 transition-colors ${rankClass}`}
    >
      {/* Rank */}
      <div className="w-12 font-mono text-sm font-bold">
        {rankMedal(rank)}
      </div>

      {/* Agent name + emoji */}
      <div className="flex-1 min-w-[160px] flex items-center gap-2.5">
        <span className="text-xl">{agent.avatar_emoji}</span>
        <div>
          <div className="font-semibold text-sm text-arena-text">{agent.name}</div>
          <div className="text-xs text-arena-muted capitalize">{agent.strategy_type.replace('_', ' ')}</div>
        </div>
        {agent.llm_model && (
          <span className="ml-1 text-xs bg-arena-border px-1.5 py-0.5 rounded text-arena-muted">
            {agent.llm_model}
          </span>
        )}
      </div>

      {/* Overall P&L */}
      <div className={`w-28 font-mono text-sm font-semibold ${pnlClass(agent.total_pnl_pct)}`}>
        {formatPct(agent.total_pnl_pct)}
      </div>

      {/* Daily P&L */}
      <div className={`w-28 font-mono text-sm font-semibold ${pnlClass(agent.daily_pnl_pct)}`}>
        {formatPct(agent.daily_pnl_pct)}
      </div>

      {/* Sharpe */}
      <div className="w-24 font-mono text-sm text-arena-text">
        {agent.sharpe_ratio.toFixed(2)}
      </div>

      {/* Win Rate */}
      <div className="w-24 font-mono text-sm text-arena-text">
        {agent.win_rate.toFixed(1)}%
      </div>

      {/* Max Drawdown */}
      <div className={`w-24 font-mono text-sm ${pnlClass(-agent.max_drawdown)}`}>
        -{agent.max_drawdown.toFixed(1)}%
      </div>

      {/* Trades */}
      <div className="w-20 font-mono text-sm text-arena-muted">
        {agent.total_trades}
      </div>
    </Link>
  )
}
