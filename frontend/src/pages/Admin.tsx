/**
 * Admin Panel — manage contests and agents.
 */
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Navigate } from 'react-router-dom'
import { api } from '@/lib/api'
import { useAuthStore } from '@/store/auth'

export default function Admin() {
  const { user, isAuthenticated } = useAuthStore()
  const queryClient = useQueryClient()

  if (!isAuthenticated || !user?.is_admin) {
    return <Navigate to="/" replace />
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-arena-text">⚙️ Admin Panel</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <AdminCard
          title="Force Settle Today's Contest"
          description="Immediately settle the daily contest and pay out winners. Use for testing."
          action={async () => {
            const { data } = await api.post('/api/betting/admin/settle')
            return data
          }}
          buttonLabel="Settle Now"
          buttonClass="bg-arena-red/10 border-arena-red/40 text-arena-red hover:bg-arena-red/20"
        />

        <AdminCard
          title="Refresh Leaderboard"
          description="Force a leaderboard recompute and push to all WebSocket clients."
          action={async () => {
            const { data } = await api.get('/api/leaderboard?period=today')
            queryClient.invalidateQueries({ queryKey: ['leaderboard'] })
            return { message: `Refreshed ${data.leaderboard.length} agents` }
          }}
          buttonLabel="Refresh"
          buttonClass="bg-arena-accent/10 border-arena-accent/40 text-arena-accent hover:bg-arena-accent/20"
        />
      </div>

      <div className="bg-arena-card border border-arena-border rounded-lg p-4 text-sm text-arena-muted">
        <p className="font-semibold text-arena-text mb-2">API Access</p>
        <p>Full API docs available at <code className="text-arena-accent">/docs</code> (dev mode only)</p>
        <p className="mt-1">All admin endpoints require <code className="text-arena-accent">is_admin=true</code> on the user account.</p>
      </div>
    </div>
  )
}

function AdminCard({
  title, description, action, buttonLabel, buttonClass
}: {
  title: string
  description: string
  action: () => Promise<{ message?: string; winning_agent?: string; [key: string]: unknown }>
  buttonLabel: string
  buttonClass: string
}) {
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const run = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await action()
      setResult(JSON.stringify(data, null, 2))
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      setError(err?.response?.data?.detail || 'Error occurred')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-arena-card border border-arena-border rounded-lg p-4 space-y-3">
      <div>
        <h3 className="font-semibold text-arena-text text-sm">{title}</h3>
        <p className="text-xs text-arena-muted mt-1">{description}</p>
      </div>
      <button
        onClick={run}
        disabled={loading}
        className={`border rounded px-4 py-2 text-sm font-semibold transition-colors disabled:opacity-50 ${buttonClass}`}
      >
        {loading ? 'Running...' : buttonLabel}
      </button>
      {result && (
        <pre className="text-xs text-arena-green bg-arena-surface rounded p-2 overflow-x-auto">
          {result}
        </pre>
      )}
      {error && (
        <p className="text-xs text-arena-red">{error}</p>
      )}
    </div>
  )
}
