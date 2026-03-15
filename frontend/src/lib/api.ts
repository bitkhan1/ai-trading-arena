/**
 * API client — thin wrapper around axios with auth token injection.
 */
import axios from 'axios'
import { useAuthStore } from '@/store/auth'

const API_BASE = import.meta.env.VITE_API_URL || ''

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 10_000,
})

// Inject JWT token on every request
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle 401 globally — log out
api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout()
    }
    return Promise.reject(error)
  },
)

// ── Leaderboard ────────────────────────────────────────────────────

export const fetchLeaderboard = async (period: string = 'all') => {
  const { data } = await api.get(`/api/leaderboard?period=${period}`)
  return data.leaderboard
}

export const fetchAgentList = async () => {
  const { data } = await api.get('/api/leaderboard/agents')
  return data.agents
}

export const fetchAgentProfile = async (agentId: number) => {
  const { data } = await api.get(`/api/agents/${agentId}/profile`)
  return data
}

export const fetchLeaderboardHistory = async (agentId?: number) => {
  const url = agentId
    ? `/api/leaderboard/history?agent_id=${agentId}`
    : '/api/leaderboard/history'
  const { data } = await api.get(url)
  return data.history
}

// ── Signals ────────────────────────────────────────────────────────

export const fetchSignalFeed = async (limit = 50, messageType?: string) => {
  const params = new URLSearchParams({ limit: String(limit) })
  if (messageType) params.set('message_type', messageType)
  const { data } = await api.get(`/api/signals/feed?${params}`)
  return data.signals
}

// ── Betting ────────────────────────────────────────────────────────

export const fetchDailyContest = async () => {
  const { data } = await api.get('/api/betting/daily-contest')
  return data
}

export const placeBet = async (agentId: number, amount: number) => {
  const { data } = await api.post('/api/betting/place', { agent_id: agentId, amount })
  return data
}

export const fetchMyBets = async () => {
  const { data } = await api.get('/api/betting/my-bets')
  return data
}

export const fetchContestHistory = async () => {
  const { data } = await api.get('/api/betting/history')
  return data.results
}

// ── Auth ────────────────────────────────────────────────────────────

export const login = async (email: string, password: string) => {
  const form = new FormData()
  form.append('username', email)
  form.append('password', password)
  const { data } = await api.post('/api/auth/token', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  return data
}

export const register = async (email: string, username: string, password: string) => {
  const { data } = await api.post('/api/auth/register', { email, username, password })
  return data
}

export const fetchMe = async () => {
  const { data } = await api.get('/api/auth/me')
  return data
}
