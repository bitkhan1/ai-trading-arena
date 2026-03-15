/**
 * User Dashboard — token balance, bet history, stats.
 */
import { useQuery } from '@tanstack/react-query'
import { Link, Navigate } from 'react-router-dom'
import { fetchMe, fetchMyBets } from '@/lib/api'
import { formatTokens, timeAgo } from '@/lib/utils'
import { useAuthStore } from '@/store/auth'

export default function Dashboard() {
  const { isAuthenticated, user } = useAuthStore()

  const { data: bets } = useQuery({
    queryKey: ['my-bets'],
    queryFn: fetchMyBets,
    enabled: isAuthenticated,
  })

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  const summary = bets?.summary

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-arena-text">My Dashboard</h1>

      {/* Token balance card */}
      <div className="bg-arena-card border border-arena-border rounded-lg p-6">
        <div className="flex items-center gap-4">
          <span className="text-5xl">🪙</span>
          <div>
            <div className="text-3xl font-bold font-mono text-arena-yellow">
              {formatTokens(user?.token_balance || 0)}
            </div>
            <div className="text-sm text-arena-muted">Arena Tokens</div>
            <div className="text-xs text-arena-muted mt-0.5">
              +100 tokens daily login bonus
            </div>
          </div>
          <div className="ml-auto">
            <Link
              to="/bet"
              className="bg-arena-yellow/10 border border-arena-yellow/40 text-arena-yellow px-4 py-2 rounded font-semibold text-sm hover:bg-arena-yellow/20 transition-colors"
            >
              Bet Now
            </Link>
          </div>
        </div>
      </div>

      {/* Stats */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard label="Total Bet" value={formatTokens(summary.total_bet)} />
          <StatCard label="Total Won" value={formatTokens(summary.total_won)} valueClass="text-arena-green" />
          <StatCard label="Wins" value={String(summary.win_count)} valueClass="text-arena-green" />
          <StatCard label="Losses" value={String(summary.loss_count)} valueClass="text-arena-red" />
        </div>
      )}

      {/* Bet history */}
      <div className="bg-arena-card border border-arena-border rounded-lg">
        <div className="px-4 py-3 border-b border-arena-border">
          <h2 className="text-sm font-semibold text-arena-text">Bet History</h2>
        </div>
        <div className="divide-y divide-arena-border/50">
          {!bets?.bets?.length ? (
            <p className="px-4 py-6 text-sm text-arena-muted text-center">
              No bets yet.{' '}
              <Link to="/bet" className="text-arena-accent hover:underline">Place your first bet!</Link>
            </p>
          ) : (
            bets.bets.map((bet: {
              id: number
              agent_name: string
              amount: number
              payout: number
              profit: number
              status: string
              placed_at: string
            }) => (
              <div key={bet.id} className="px-4 py-3 flex items-center gap-3">
                <div className="flex-1">
                  <div className="text-sm font-semibold text-arena-text">{bet.agent_name}</div>
                  <div className="text-xs text-arena-muted">{timeAgo(bet.placed_at)}</div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-mono text-arena-muted">
                    {formatTokens(bet.amount)} bet
                  </div>
                  <div className={`text-sm font-mono font-semibold ${
                    bet.status === 'won' ? 'text-arena-green' :
                    bet.status === 'lost' ? 'text-arena-red' : 'text-arena-muted'
                  }`}>
                    {bet.status === 'won' ? `+${formatTokens(bet.payout)} won` :
                     bet.status === 'lost' ? 'Lost' :
                     'Pending'}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Account info */}
      <div className="bg-arena-card border border-arena-border rounded-lg p-4 text-sm text-arena-muted">
        <p>Logged in as <strong className="text-arena-text">{user?.username}</strong></p>
        <p className="mt-1">Email: {user?.email}</p>
        <p className="mt-3 text-xs">
          Arena Tokens are virtual currency with no monetary value.
          They cannot be withdrawn, exchanged, or transferred.
        </p>
      </div>
    </div>
  )
}

function StatCard({ label, value, valueClass = 'text-arena-text' }: {
  label: string; value: string; valueClass?: string
}) {
  return (
    <div className="bg-arena-card border border-arena-border rounded-lg p-3 text-center">
      <div className={`text-xl font-bold font-mono ${valueClass}`}>{value}</div>
      <div className="text-xs text-arena-muted mt-0.5">{label}</div>
    </div>
  )
}
