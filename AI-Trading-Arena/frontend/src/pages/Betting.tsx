/**
 * Betting Page — Arena Token daily contest.
 * Users pick one agent and bet tokens. Winners split the pot at market close.
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSearchParams, Link } from 'react-router-dom'
import { fetchDailyContest, placeBet, fetchContestHistory, fetchMyBets } from '@/lib/api'
import { formatPct, pnlClass, formatTokens, timeAgo } from '@/lib/utils'
import { useAuthStore } from '@/store/auth'
import type { ContestAgent, DailyContest, ContestResult } from '@/types'

export default function Betting() {
  const { isAuthenticated, user, updateBalance } = useAuthStore()
  const [searchParams] = useSearchParams()
  const preselectedAgent = searchParams.get('agent')
  const [selectedAgent, setSelectedAgent] = useState<number | null>(
    preselectedAgent ? parseInt(preselectedAgent) : null
  )
  const [betAmount, setBetAmount] = useState(100)
  const [tab, setTab] = useState<'contest' | 'history' | 'mybets'>('contest')
  const queryClient = useQueryClient()

  const { data: contest, isLoading } = useQuery<DailyContest>({
    queryKey: ['daily-contest'],
    queryFn: fetchDailyContest,
    refetchInterval: 15_000,
    enabled: isAuthenticated,
  })

  const { data: history } = useQuery<ContestResult[]>({
    queryKey: ['contest-history'],
    queryFn: fetchContestHistory,
    enabled: tab === 'history',
  })

  const { data: myBets } = useQuery({
    queryKey: ['my-bets'],
    queryFn: fetchMyBets,
    enabled: tab === 'mybets' && isAuthenticated,
  })

  const betMutation = useMutation({
    mutationFn: () => placeBet(selectedAgent!, betAmount),
    onSuccess: (data) => {
      updateBalance(data.remaining_balance)
      queryClient.invalidateQueries({ queryKey: ['daily-contest'] })
      queryClient.invalidateQueries({ queryKey: ['my-bets'] })
    },
  })

  if (!isAuthenticated) {
    return (
      <div className="max-w-md mx-auto text-center py-20 space-y-4">
        <p className="text-6xl">🪙</p>
        <h2 className="text-xl font-bold text-arena-text">Sign in to Bet</h2>
        <p className="text-arena-muted text-sm">You get 5,000 free Arena Tokens on sign up</p>
        <Link to="/login" className="inline-block bg-arena-accent text-arena-bg px-6 py-2.5 rounded font-semibold hover:bg-arena-accent/90 transition-colors">
          Sign In
        </Link>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-arena-text">🪙 Daily Contest</h1>
        {user && (
          <div className="flex items-center gap-1.5 bg-arena-card border border-arena-border rounded px-3 py-1.5">
            <span className="text-arena-yellow">🪙</span>
            <span className="font-mono font-semibold text-arena-text">{formatTokens(user.token_balance)}</span>
            <span className="text-xs text-arena-muted ml-1">tokens</span>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-arena-border">
        {(['contest', 'history', 'mybets'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t ? 'border-arena-accent text-arena-accent' : 'border-transparent text-arena-muted hover:text-arena-text'
            }`}
          >
            {t === 'contest' ? "Today's Contest" : t === 'history' ? 'Past Results' : 'My Bets'}
          </button>
        ))}
      </div>

      {/* Contest tab */}
      {tab === 'contest' && (
        <div className="space-y-4">
          {/* Rules */}
          <div className="bg-arena-card border border-arena-border rounded-lg p-4 text-sm text-arena-muted space-y-1">
            <p className="text-arena-text font-semibold">How it works:</p>
            <p>1. Pick one agent and bet any amount of your Arena Tokens.</p>
            <p>2. At market close, the agent with the highest <strong className="text-arena-text">Daily P&L%</strong> wins.</p>
            <p>3. Winners split <strong className="text-arena-text">95% of the total pot</strong> proportionally.</p>
            <p className="text-arena-muted text-xs mt-1">Arena Tokens have no monetary value. For entertainment only.</p>
          </div>

          {isLoading ? (
            <div className="text-center py-8 text-arena-muted animate-pulse">Loading contest...</div>
          ) : !contest ? (
            <div className="text-center py-8 text-arena-muted">No contest available</div>
          ) : (
            <>
              {/* Existing bet */}
              {contest.user_bet && (
                <div className="bg-arena-green/5 border border-arena-green/30 rounded-lg p-4">
                  <p className="text-arena-green font-semibold text-sm">
                    ✓ Bet placed: {formatTokens(contest.user_bet.amount)} tokens on {contest.user_bet.agent_name}
                  </p>
                  <p className="text-arena-muted text-xs mt-1">
                    Status: {contest.user_bet.status} · Placed {timeAgo(contest.user_bet.placed_at)}
                  </p>
                </div>
              )}

              {/* Contest stats */}
              <div className="grid grid-cols-3 gap-3">
                <div className="bg-arena-card border border-arena-border rounded-lg p-3 text-center">
                  <div className="text-xl font-bold font-mono text-arena-text">
                    {formatTokens(contest.total_pot)}
                  </div>
                  <div className="text-xs text-arena-muted mt-0.5">Total Pot</div>
                </div>
                <div className="bg-arena-card border border-arena-border rounded-lg p-3 text-center">
                  <div className="text-xl font-bold font-mono text-arena-text">
                    {contest.total_bettors}
                  </div>
                  <div className="text-xs text-arena-muted mt-0.5">Bettors</div>
                </div>
                <div className="bg-arena-card border border-arena-border rounded-lg p-3 text-center">
                  <div className={`text-sm font-semibold font-mono ${
                    contest.status === 'open' ? 'text-arena-green' : 'text-arena-yellow'
                  }`}>
                    {contest.status.toUpperCase()}
                  </div>
                  <div className="text-xs text-arena-muted mt-0.5">Status</div>
                </div>
              </div>

              {/* Agent list */}
              {!contest.user_bet && contest.status === 'open' && (
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-arena-text">Pick your agent:</h3>
                  <div className="space-y-2">
                    {contest.agents.map((agent) => (
                      <AgentBetCard
                        key={agent.id}
                        agent={agent}
                        selected={selectedAgent === agent.id}
                        onSelect={() => setSelectedAgent(agent.id)}
                      />
                    ))}
                  </div>

                  {/* Bet amount + submit */}
                  {selectedAgent && (
                    <div className="bg-arena-card border border-arena-border rounded-lg p-4 space-y-3">
                      <h3 className="text-sm font-semibold text-arena-text">
                        Bet amount (you have {formatTokens(user?.token_balance || 0)} tokens)
                      </h3>
                      <div className="flex gap-2">
                        <input
                          type="number"
                          min={1}
                          max={user?.token_balance || 0}
                          value={betAmount}
                          onChange={(e) => setBetAmount(Math.max(1, parseInt(e.target.value) || 1))}
                          className="flex-1 bg-arena-surface border border-arena-border rounded px-3 py-2 text-arena-text font-mono text-sm focus:outline-none focus:border-arena-accent"
                        />
                        {[100, 500, 1000, 5000].map((amt) => (
                          <button
                            key={amt}
                            onClick={() => setBetAmount(Math.min(amt, user?.token_balance || 0))}
                            className="text-xs px-2 py-1 bg-arena-surface border border-arena-border rounded text-arena-muted hover:text-arena-text transition-colors"
                          >
                            {formatTokens(amt)}
                          </button>
                        ))}
                      </div>
                      <button
                        onClick={() => betMutation.mutate()}
                        disabled={betMutation.isPending || !selectedAgent || betAmount <= 0}
                        className="w-full bg-arena-accent text-arena-bg py-2.5 rounded font-semibold text-sm hover:bg-arena-accent/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {betMutation.isPending ? 'Placing bet...' : `Bet ${formatTokens(betAmount)} tokens`}
                      </button>
                      {betMutation.isError && (
                        <p className="text-arena-red text-xs">
                          {(betMutation.error as Error & { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to place bet'}
                        </p>
                      )}
                      {betMutation.isSuccess && (
                        <p className="text-arena-green text-xs">
                          {betMutation.data?.message}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* History tab */}
      {tab === 'history' && (
        <div className="space-y-2">
          {!history?.length ? (
            <p className="text-arena-muted text-sm text-center py-8">No past contests yet</p>
          ) : (
            history.map((result, i) => (
              <div key={i} className="bg-arena-card border border-arena-border rounded-lg p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-arena-text">{result.contest_date}</p>
                    <p className="text-xs text-arena-muted">
                      Winner: <span className="text-arena-text">{result.winning_agent}</span>
                      {' '}(<span className={pnlClass(result.winning_pnl_pct)}>{formatPct(result.winning_pnl_pct)}</span>)
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-mono font-semibold text-arena-text">
                      {formatTokens(result.total_pot)} tokens
                    </p>
                    <p className="text-xs text-arena-muted">
                      {result.winning_bettors}/{result.total_bettors} won
                    </p>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* My bets tab */}
      {tab === 'mybets' && (
        <div className="space-y-2">
          {!myBets?.bets?.length ? (
            <p className="text-arena-muted text-sm text-center py-8">No bets yet</p>
          ) : (
            <>
              {/* Summary */}
              <div className="grid grid-cols-3 gap-3 mb-4">
                <div className="bg-arena-card border border-arena-border rounded-lg p-3 text-center">
                  <div className="text-lg font-bold font-mono text-arena-text">
                    {myBets.summary.win_count}
                  </div>
                  <div className="text-xs text-arena-green">Wins</div>
                </div>
                <div className="bg-arena-card border border-arena-border rounded-lg p-3 text-center">
                  <div className="text-lg font-bold font-mono text-arena-text">
                    {myBets.summary.loss_count}
                  </div>
                  <div className="text-xs text-arena-red">Losses</div>
                </div>
                <div className="bg-arena-card border border-arena-border rounded-lg p-3 text-center">
                  <div className={`text-lg font-bold font-mono ${
                    myBets.summary.total_won - myBets.summary.total_lost >= 0 ? 'text-arena-green' : 'text-arena-red'
                  }`}>
                    {myBets.summary.total_won - myBets.summary.total_lost >= 0 ? '+' : ''}
                    {formatTokens(myBets.summary.total_won - myBets.summary.total_lost)}
                  </div>
                  <div className="text-xs text-arena-muted">Net P&L</div>
                </div>
              </div>

              {myBets.bets.map((bet: ReturnType<typeof myBets.bets>[number]) => (
                <div key={bet.id} className="bg-arena-card border border-arena-border rounded-lg p-4 flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-arena-text">{bet.agent_name}</p>
                    <p className="text-xs text-arena-muted">{timeAgo(bet.placed_at)}</p>
                  </div>
                  <div className="text-right">
                    <p className={`text-sm font-mono font-semibold ${
                      bet.status === 'won' ? 'text-arena-green' :
                      bet.status === 'lost' ? 'text-arena-red' : 'text-arena-muted'
                    }`}>
                      {bet.status === 'won' ? `+${formatTokens(bet.payout)}` :
                       bet.status === 'lost' ? `-${formatTokens(bet.amount)}` :
                       formatTokens(bet.amount)}
                    </p>
                    <p className="text-xs text-arena-muted capitalize">{bet.status}</p>
                  </div>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  )
}


function AgentBetCard({ agent, selected, onSelect }: {
  agent: ContestAgent
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      onClick={onSelect}
      className={`w-full text-left bg-arena-card border rounded-lg p-3 flex items-center gap-3 transition-all
        ${selected ? 'border-arena-accent shadow-[0_0_0_1px_#58a6ff]' : 'border-arena-border hover:border-arena-border/80'}`}
    >
      <span className="text-2xl">{agent.avatar_emoji}</span>
      <div className="flex-1">
        <div className="font-semibold text-sm text-arena-text">{agent.name}</div>
        <div className="text-xs text-arena-muted capitalize">{agent.strategy_type.replace('_', ' ')}</div>
      </div>
      <div className="text-right">
        <div className={`font-mono text-sm font-bold ${pnlClass(agent.daily_pnl_pct)}`}>
          {formatPct(agent.daily_pnl_pct)}
        </div>
        <div className="text-xs text-arena-muted">today</div>
      </div>
      {selected && (
        <div className="w-5 h-5 rounded-full bg-arena-accent flex items-center justify-center shrink-0">
          <span className="text-arena-bg text-xs">✓</span>
        </div>
      )}
    </button>
  )
}
