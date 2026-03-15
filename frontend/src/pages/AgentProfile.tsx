/**
 * Agent Profile Page — strategy card, equity curve, trade history.
 */
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine
} from 'recharts'
import { fetchAgentProfile } from '@/lib/api'
import { formatPct, formatCurrency, pnlClass, timeAgo } from '@/lib/utils'
import type { AgentProfile, Trade, Position } from '@/types'

export default function AgentProfile() {
  const { agentId } = useParams<{ agentId: string }>()

  const { data: agent, isLoading, error } = useQuery<AgentProfile>({
    queryKey: ['agent', agentId],
    queryFn: () => fetchAgentProfile(parseInt(agentId!)),
    refetchInterval: 30_000,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-40">
        <div className="text-arena-muted animate-pulse">Loading agent profile...</div>
      </div>
    )
  }

  if (error || !agent) {
    return (
      <div className="text-center py-40">
        <p className="text-arena-red">Agent not found</p>
        <Link to="/" className="text-arena-accent hover:underline mt-2 block">← Back to Leaderboard</Link>
      </div>
    )
  }

  const equity = agent.cash + (agent.positions_value || 0)

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Back */}
      <Link to="/" className="text-sm text-arena-muted hover:text-arena-text flex items-center gap-1">
        ← Leaderboard
      </Link>

      {/* Profile header */}
      <div className="bg-arena-card border border-arena-border rounded-lg p-6">
        <div className="flex flex-col sm:flex-row sm:items-start gap-4">
          <div className="text-6xl">{agent.avatar_emoji}</div>
          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-bold text-arena-text">{agent.name}</h1>
              {agent.llm_model && (
                <span className="text-xs bg-arena-border px-2 py-1 rounded text-arena-muted">
                  {agent.llm_model}
                </span>
              )}
              <span className={`text-xs px-2 py-1 rounded font-medium ${
                agent.status === 'active' ? 'bg-arena-green/10 text-arena-green' : 'bg-arena-red/10 text-arena-red'
              }`}>
                {agent.status}
              </span>
            </div>
            <p className="text-sm text-arena-muted mt-1 capitalize">
              Strategy: <span className="text-arena-text">{agent.strategy_type.replace(/_/g, ' ')}</span>
            </p>
            {agent.description && (
              <p className="text-sm text-arena-muted mt-2 leading-relaxed">{agent.description}</p>
            )}
          </div>

          {/* P&L badge */}
          <div className="text-right">
            <div className={`text-3xl font-bold font-mono ${pnlClass(agent.daily_pnl_pct)}`}>
              {formatPct(agent.daily_pnl_pct)}
            </div>
            <div className="text-xs text-arena-muted">Today's P&L</div>
            <div className={`text-lg font-mono font-semibold mt-1 ${pnlClass(agent.total_pnl_pct)}`}>
              {formatPct(agent.total_pnl_pct)}
            </div>
            <div className="text-xs text-arena-muted">All-Time P&L</div>
          </div>
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6 pt-6 border-t border-arena-border">
          <StatBox label="Portfolio Value" value={formatCurrency(equity)} />
          <StatBox label="Sharpe Ratio" value={agent.sharpe_ratio.toFixed(2)} />
          <StatBox label="Win Rate" value={`${agent.win_rate.toFixed(1)}%`} />
          <StatBox label="Max Drawdown" value={`-${agent.max_drawdown.toFixed(1)}%`} valueClass="text-arena-red" />
        </div>
      </div>

      {/* Equity curve */}
      {agent.equity_history && agent.equity_history.length > 2 && (
        <div className="bg-arena-card border border-arena-border rounded-lg p-4">
          <h2 className="text-sm font-semibold text-arena-muted mb-3">Equity Curve</h2>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={agent.equity_history}>
              <CartesianGrid strokeDasharray="3 3" stroke="#30363d" />
              <XAxis dataKey="timestamp" hide />
              <YAxis
                domain={['auto', 'auto']}
                tickFormatter={(v: number) => `$${(v/1000).toFixed(0)}K`}
                stroke="#7d8590"
                tick={{ fill: '#7d8590', fontSize: 11 }}
              />
              <Tooltip
                contentStyle={{ background: '#1c2128', border: '1px solid #30363d', borderRadius: 6 }}
                labelStyle={{ color: '#7d8590' }}
                formatter={(v: number) => [formatCurrency(v), 'Portfolio']}
              />
              <ReferenceLine y={100000} stroke="#30363d" strokeDasharray="4 4" />
              <Line
                type="monotone"
                dataKey="equity"
                stroke={agent.total_pnl_pct >= 0 ? '#3fb950' : '#f85149'}
                dot={false}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Two column: positions + recent trades */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Open positions */}
        <div className="bg-arena-card border border-arena-border rounded-lg">
          <h2 className="px-4 py-3 border-b border-arena-border text-sm font-semibold text-arena-text">
            Open Positions ({agent.open_positions?.length || 0})
          </h2>
          <div className="divide-y divide-arena-border/50">
            {!agent.open_positions?.length ? (
              <p className="px-4 py-4 text-sm text-arena-muted">No open positions</p>
            ) : (
              agent.open_positions.map((pos) => (
                <PositionRow key={pos.symbol} position={pos} />
              ))
            )}
          </div>
        </div>

        {/* Recent trades */}
        <div className="bg-arena-card border border-arena-border rounded-lg">
          <h2 className="px-4 py-3 border-b border-arena-border text-sm font-semibold text-arena-text">
            Recent Trades
          </h2>
          <div className="divide-y divide-arena-border/50 max-h-80 overflow-y-auto">
            {!agent.recent_trades?.length ? (
              <p className="px-4 py-4 text-sm text-arena-muted">No trades yet</p>
            ) : (
              agent.recent_trades.map((trade) => (
                <TradeRow key={trade.id} trade={trade} />
              ))
            )}
          </div>
        </div>
      </div>

      {/* Bet CTA */}
      <div className="bg-arena-card border border-arena-border rounded-lg p-5 flex items-center justify-between gap-4">
        <div>
          <p className="font-semibold text-arena-text">Believe in this agent?</p>
          <p className="text-sm text-arena-muted">Bet Arena Tokens on {agent.name} to win today</p>
        </div>
        <Link
          to={`/bet?agent=${agent.id}`}
          className="bg-arena-yellow/10 border border-arena-yellow/40 text-arena-yellow px-4 py-2 rounded font-semibold text-sm hover:bg-arena-yellow/20 transition-colors whitespace-nowrap"
        >
          🪙 Bet on This Agent
        </Link>
      </div>
    </div>
  )
}

function StatBox({ label, value, valueClass = 'text-arena-text' }: {
  label: string; value: string; valueClass?: string
}) {
  return (
    <div>
      <div className="text-xs text-arena-muted">{label}</div>
      <div className={`text-lg font-mono font-semibold mt-0.5 ${valueClass}`}>{value}</div>
    </div>
  )
}

function PositionRow({ position }: { position: Position }) {
  return (
    <div className="px-4 py-2.5 flex items-center justify-between gap-2 text-sm">
      <div>
        <span className="font-mono font-semibold text-arena-text">{position.symbol}</span>
        <span className="text-xs text-arena-muted ml-2">{position.quantity} shares</span>
      </div>
      <div className="text-right">
        <div className={`font-mono text-sm font-semibold ${pnlClass(position.pnl)}`}>
          {formatPct(position.pnl_pct)}
        </div>
        <div className="text-xs text-arena-muted">@ ${position.entry_price.toFixed(2)}</div>
      </div>
    </div>
  )
}

function TradeRow({ trade }: { trade: Trade }) {
  const isBuy = ['buy', 'cover'].includes(trade.action)
  return (
    <div className="px-4 py-2.5 text-sm">
      <div className="flex items-center gap-2 mb-0.5">
        <span className={`font-mono font-bold text-xs uppercase ${isBuy ? 'text-arena-green' : 'text-arena-red'}`}>
          {trade.action}
        </span>
        <span className="font-mono text-arena-text">{trade.quantity} {trade.symbol}</span>
        <span className="text-arena-muted">@</span>
        <span className="font-mono text-arena-text">${trade.price.toFixed(2)}</span>
        <span className="ml-auto text-xs text-arena-muted">{timeAgo(trade.executed_at)}</span>
      </div>
      {trade.reasoning && (
        <p className="text-xs text-arena-muted line-clamp-1">{trade.reasoning}</p>
      )}
    </div>
  )
}
