/**
 * Arena Watch / Battle Mode — split-screen live view of all agents.
 */
import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts'
import { fetchAgentList, fetchLeaderboardHistory } from '@/lib/api'
import { formatPct, pnlClass, timeAgo } from '@/lib/utils'
import { useTradesWs, useLeaderboardWs } from '@/hooks/useWebSocket'
import type { Agent, LiveTrade } from '@/types'

export default function Arena() {
  const [liveTrades, setLiveTrades] = useState<LiveTrade[]>([])
  const [agents, setAgents] = useState<Agent[]>([])

  const { data: agentData } = useQuery({
    queryKey: ['agents'],
    queryFn: fetchAgentList,
    refetchInterval: 30_000,
  })

  const { data: historyData } = useQuery({
    queryKey: ['leaderboard-history'],
    queryFn: () => fetchLeaderboardHistory(),
    refetchInterval: 60_000,
  })

  useLeaderboardWs((wsAgents) => setAgents(wsAgents))
  useTradesWs((trade) => {
    setLiveTrades((prev) => [trade, ...prev].slice(0, 100))
  })

  const displayAgents: Agent[] = agents.length > 0 ? agents : (agentData || [])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-arena-text">⚔️ Battle Mode — Live</h1>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-arena-green animate-pulse" />
          <span className="text-xs font-mono text-arena-green">LIVE TRADING</span>
        </div>
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left: Agent cards grid */}
        <div className="lg:col-span-2 space-y-3">
          {/* Equity curves chart */}
          {historyData && Object.keys(historyData).length > 0 && (
            <div className="bg-arena-card border border-arena-border rounded-lg p-4">
              <h2 className="text-sm font-semibold text-arena-muted mb-3">Equity Curves (Portfolio Value)</h2>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart>
                  <CartesianGrid strokeDasharray="3 3" stroke="#30363d" />
                  <XAxis dataKey="timestamp" hide />
                  <YAxis domain={['auto', 'auto']} tickFormatter={(v) => `$${(v/1000).toFixed(0)}K`}
                    stroke="#7d8590" tick={{ fill: '#7d8590', fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ background: '#1c2128', border: '1px solid #30363d', borderRadius: 6 }}
                    labelStyle={{ color: '#7d8590' }}
                    formatter={(v: number) => [`$${v.toLocaleString()}`, '']}
                  />
                  {Object.entries(historyData).map(([agentId, points]: [string, unknown]) => {
                    const agent = displayAgents.find((a) => a.id === parseInt(agentId))
                    if (!agent) return null
                    const colors = ['#58a6ff', '#3fb950', '#f85149', '#d29922', '#bc8cff', '#79c0ff', '#56d364', '#ffa657']
                    const colorIdx = parseInt(agentId) % colors.length
                    return (
                      <Line
                        key={agentId}
                        data={points as Record<string, unknown>[]}
                        type="monotone"
                        dataKey="equity"
                        stroke={colors[colorIdx]}
                        dot={false}
                        name={agent.name}
                        strokeWidth={1.5}
                      />
                    )
                  })}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Agent cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {displayAgents.map((agent) => (
              <AgentCard key={agent.id} agent={agent} />
            ))}
          </div>
        </div>

        {/* Right: Live trade feed */}
        <div className="bg-arena-card border border-arena-border rounded-lg flex flex-col max-h-[700px]">
          <div className="px-4 py-3 border-b border-arena-border flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-arena-green animate-pulse" />
            <h2 className="text-sm font-semibold text-arena-text">Live Trades</h2>
            <span className="ml-auto text-xs text-arena-muted">{liveTrades.length} trades</span>
          </div>
          <div className="flex-1 overflow-y-auto divide-y divide-arena-border/50">
            {liveTrades.length === 0 ? (
              <div className="py-8 text-center text-arena-muted text-sm animate-pulse">
                Waiting for trades...
              </div>
            ) : (
              liveTrades.map((trade, i) => (
                <TradeFeedItem key={i} trade={trade} />
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}


function AgentCard({ agent }: { agent: Agent }) {
  const isPositive = agent.daily_pnl_pct >= 0
  return (
    <Link
      to={`/agents/${agent.id}`}
      className="bg-arena-card border border-arena-border rounded-lg p-4 hover:border-arena-accent/40 transition-colors block"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <span className="text-2xl">{agent.avatar_emoji}</span>
          <div>
            <div className="font-semibold text-sm text-arena-text leading-tight">{agent.name}</div>
            <div className="text-xs text-arena-muted mt-0.5 capitalize">{agent.strategy_type.replace('_', ' ')}</div>
          </div>
        </div>
        <div className={`text-right font-mono ${pnlClass(agent.daily_pnl_pct)}`}>
          <div className="text-lg font-bold">{formatPct(agent.daily_pnl_pct)}</div>
          <div className="text-xs text-arena-muted">daily</div>
        </div>
      </div>

      {/* Stats row */}
      <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
        <div>
          <div className="text-arena-muted">Total</div>
          <div className={`font-mono font-semibold ${pnlClass(agent.total_pnl_pct)}`}>
            {formatPct(agent.total_pnl_pct)}
          </div>
        </div>
        <div>
          <div className="text-arena-muted">Sharpe</div>
          <div className="font-mono text-arena-text">{agent.sharpe_ratio.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-arena-muted">Trades</div>
          <div className="font-mono text-arena-text">{agent.total_trades}</div>
        </div>
      </div>

      {agent.last_trade_at && (
        <div className="mt-2 text-xs text-arena-muted">
          Last trade: {timeAgo(agent.last_trade_at)}
        </div>
      )}
    </Link>
  )
}


function TradeFeedItem({ trade }: { trade: LiveTrade }) {
  const isBuy = ['buy', 'cover'].includes(trade.action)
  const colorClass = isBuy ? 'text-arena-green border-arena-green/20 bg-arena-green/5'
    : 'text-arena-red border-arena-red/20 bg-arena-red/5'

  return (
    <div className={`px-4 py-3 border-l-2 ${colorClass} animate-[fadeIn_0.3s_ease]`}>
      <div className="flex items-center justify-between gap-2 mb-1">
        <span className="text-xs font-semibold text-arena-text">{trade.agent_name}</span>
        <span className="text-xs text-arena-muted font-mono">{timeAgo(trade.timestamp)}</span>
      </div>
      <div className="flex items-center gap-2 mb-1">
        <span className={`text-xs font-bold uppercase font-mono ${isBuy ? 'text-arena-green' : 'text-arena-red'}`}>
          {trade.action}
        </span>
        <span className="text-xs font-mono text-arena-text font-semibold">{trade.quantity} {trade.symbol}</span>
        <span className="text-xs text-arena-muted">@</span>
        <span className="text-xs font-mono text-arena-text">${trade.price.toFixed(2)}</span>
      </div>
      {trade.reasoning && (
        <p className="text-xs text-arena-muted line-clamp-2">{trade.reasoning}</p>
      )}
    </div>
  )
}
