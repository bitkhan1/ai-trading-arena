/**
 * Live trade ticker — scrolling banner at the top of every page.
 * "Momentum Trader just bought 150 AAPL @ $237.45 — reasoning: strong breakout"
 */
import { useState, useEffect } from 'react'
import { useTradesWs } from '@/hooks/useWebSocket'
import type { LiveTrade } from '@/types'

function TradeChip({ trade }: { trade: LiveTrade }) {
  const isBuy = ['buy', 'cover'].includes(trade.action)
  const color = isBuy ? 'text-arena-green' : 'text-arena-red'
  const arrow = isBuy ? '▲' : '▼'

  return (
    <span className="inline-flex items-center gap-1.5 mx-8 text-xs font-mono whitespace-nowrap">
      <span className="text-arena-accent font-semibold">{trade.agent_name}</span>
      <span className={`font-bold ${color}`}>{arrow} {trade.action.toUpperCase()}</span>
      <span className="text-arena-text">{trade.quantity} {trade.symbol}</span>
      <span className="text-arena-muted">@</span>
      <span className="text-arena-text">${trade.price.toFixed(2)}</span>
      {trade.reasoning && (
        <span className="text-arena-muted">— {trade.reasoning.slice(0, 60)}{trade.reasoning.length > 60 ? '…' : ''}</span>
      )}
    </span>
  )
}

export default function LiveTickerBar() {
  const [trades, setTrades] = useState<LiveTrade[]>([])

  useTradesWs((trade) => {
    setTrades((prev) => [trade, ...prev].slice(0, 30))
  })

  if (trades.length === 0) {
    return (
      <div className="bg-arena-surface border-b border-arena-border h-8 flex items-center px-4 overflow-hidden">
        <span className="text-xs text-arena-muted font-mono animate-pulse">
          ⚡ Connecting to live trade stream...
        </span>
      </div>
    )
  }

  return (
    <div className="bg-arena-surface border-b border-arena-border h-8 flex items-center overflow-hidden">
      <div className="shrink-0 flex items-center px-3 gap-1 border-r border-arena-border h-full">
        <span className="w-2 h-2 rounded-full bg-arena-green animate-pulse" />
        <span className="text-xs font-mono text-arena-green font-semibold">LIVE</span>
      </div>
      <div className="ticker-wrap flex-1">
        <div className="ticker-content">
          {trades.map((t) => (
            <TradeChip key={`${t.agent_id}-${t.timestamp}`} trade={t} />
          ))}
        </div>
      </div>
    </div>
  )
}
