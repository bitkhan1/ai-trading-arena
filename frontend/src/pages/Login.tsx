/**
 * Login / Register page.
 */
import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { login, register, api } from '@/lib/api'
import { useAuthStore } from '@/store/auth'
import type { AuthResponse, User } from '@/types'

export default function Login() {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const { setAuth } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      let authData: AuthResponse
      if (mode === 'login') {
        authData = await login(email, password)
      } else {
        authData = await register(email, username, password)
      }

      // Inject token into axios immediately so all subsequent requests are authenticated
      api.defaults.headers.common['Authorization'] = `Bearer ${authData.access_token}`

      // Build user profile directly from auth response — avoids a fetchMe round-trip
      // where the token might not yet be available in the interceptor
      const userProfile: User = {
        id: authData.user_id,
        email: email,
        username: authData.username,
        display_name: authData.username,
        token_balance: authData.token_balance,
        total_tokens_won: 0,
        total_tokens_bet: 0,
        is_admin: authData.is_admin,
      }

      setAuth(authData, userProfile)

      // Small tick so Zustand can persist to localStorage before navigation
      await new Promise(r => setTimeout(r, 50))

      navigate('/', { replace: true })
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: string } } }
      setError(axiosError.response?.data?.detail || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-arena-bg flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <Link to="/" className="text-3xl font-bold font-mono text-arena-accent">
            ⚔️ Arena
          </Link>
          <p className="text-arena-muted text-sm mt-2">
            Fantasy football for algo trading nerds
          </p>
        </div>

        <div className="bg-arena-card border border-arena-border rounded-lg p-6">
          {/* Mode tabs */}
          <div className="flex gap-1 mb-6 bg-arena-surface rounded p-1">
            <button
              onClick={() => setMode('login')}
              className={`flex-1 py-1.5 text-sm font-medium rounded transition-colors ${
                mode === 'login' ? 'bg-arena-card text-arena-text' : 'text-arena-muted hover:text-arena-text'
              }`}
            >
              Sign In
            </button>
            <button
              onClick={() => setMode('register')}
              className={`flex-1 py-1.5 text-sm font-medium rounded transition-colors ${
                mode === 'register' ? 'bg-arena-card text-arena-text' : 'text-arena-muted hover:text-arena-text'
              }`}
            >
              Create Account
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-arena-muted mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full bg-arena-surface border border-arena-border rounded px-3 py-2 text-arena-text text-sm focus:outline-none focus:border-arena-accent"
                placeholder="you@example.com"
              />
            </div>

            {mode === 'register' && (
              <div>
                <label className="block text-xs font-medium text-arena-muted mb-1">Username</label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  minLength={3}
                  className="w-full bg-arena-surface border border-arena-border rounded px-3 py-2 text-arena-text text-sm focus:outline-none focus:border-arena-accent"
                  placeholder="tradingwizard"
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-arena-muted mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                className="w-full bg-arena-surface border border-arena-border rounded px-3 py-2 text-arena-text text-sm focus:outline-none focus:border-arena-accent"
                placeholder="••••••••"
              />
            </div>

            {error && (
              <p className="text-arena-red text-xs bg-arena-red/10 border border-arena-red/30 rounded px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-arena-accent text-arena-bg py-2.5 rounded font-semibold text-sm hover:bg-arena-accent/90 transition-colors disabled:opacity-50"
            >
              {loading ? 'Loading...' : mode === 'login' ? 'Sign In' : 'Create Account + Get 5,000 Tokens'}
            </button>
          </form>

          {mode === 'register' && (
            <p className="text-xs text-arena-muted text-center mt-4">
              New accounts receive 5,000 Arena Tokens (no real money value).
            </p>
          )}
        </div>

        <p className="text-center text-xs text-arena-muted mt-4">
          <Link to="/" className="hover:text-arena-text">← Back to Arena</Link>
        </p>
      </div>
    </div>
  )
}
