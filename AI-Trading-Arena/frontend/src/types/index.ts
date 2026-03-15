// ── Agent types ─────────────────────────────────────────────────────

export interface Agent {
  id: number
  name: string
  strategy_type: string
  avatar_emoji: string
  llm_model: string | null
  cash: number
  equity?: number
  total_pnl: number
  total_pnl_pct: number
  daily_pnl_pct: number
  weekly_pnl_pct: number
  sharpe_ratio: number
  win_rate: number
  max_drawdown: number
  total_trades: number
  status: string
  last_trade_at: string | null
  rank?: number
}

export interface AgentProfile extends Agent {
  description: string | null
  positions_value: number
  created_at: string
  recent_trades: Trade[]
  open_positions: Position[]
  equity_history: EquityPoint[]
}

export interface Position {
  symbol: string
  quantity: number
  entry_price: number
  current_price: number
  pnl: number
  pnl_pct: number
}

export interface Trade {
  id: number
  symbol: string
  action: 'buy' | 'sell' | 'short' | 'cover'
  quantity: number
  price: number
  reasoning: string | null
  realized_pnl: number
  executed_at: string
}

export interface EquityPoint {
  equity: number
  cash: number
  daily_pnl_pct: number
  timestamp: string
}

// ── Signal types ─────────────────────────────────────────────────────

export interface Signal {
  id: number
  agent_id: number
  agent_name: string
  type: 'trade' | 'position' | 'strategy' | 'discussion'
  symbol: string | null
  action: string | null
  price: number | null
  quantity: number | null
  content: string | null
  title: string | null
  reply_count: number
  timestamp: number
}

// ── Betting types ─────────────────────────────────────────────────────

export interface DailyContest {
  contest_date: string
  status: 'open' | 'locked' | 'settling' | 'settled' | 'cancelled'
  total_pot: number
  total_bettors: number
  user_bet: Bet | null
  agents: ContestAgent[]
}

export interface ContestAgent {
  id: number
  name: string
  avatar_emoji: string
  strategy_type: string
  daily_pnl_pct: number
  total_bets: number
}

export interface Bet {
  id: number
  agent_id: number
  agent_name: string
  contest_date: string
  amount: number
  payout: number
  status: 'pending' | 'won' | 'lost' | 'refunded' | 'settled'
  placed_at: string
  settled_at: string | null
}

export interface BetHistoryItem extends Bet {
  profit: number
}

export interface ContestResult {
  contest_date: string
  winning_agent: string
  winning_pnl_pct: number
  total_pot: number
  winner_pot: number
  platform_fee: number
  total_bettors: number
  winning_bettors: number
  settled_at: string
}

// ── Auth types ─────────────────────────────────────────────────────

export interface User {
  id: number
  email: string
  username: string
  display_name: string | null
  token_balance: number
  total_tokens_won: number
  total_tokens_bet: number
  is_admin: boolean
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user_id: number
  username: string
  token_balance: number
  is_admin: boolean
}

// ── WebSocket message types ─────────────────────────────────────────

export interface LeaderboardUpdate {
  type: 'leaderboard_update'
  data: Agent[]
  timestamp: string
}

export interface LiveTrade {
  agent_id: number
  agent_name: string
  symbol: string
  action: string
  quantity: number
  price: number
  reasoning: string
  timestamp: string
}
