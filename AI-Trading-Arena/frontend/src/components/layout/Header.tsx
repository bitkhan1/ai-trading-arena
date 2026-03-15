import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/store/auth'
import { formatTokens } from '@/lib/utils'

const NAV_LINKS = [
  { to: '/', label: 'Leaderboard' },
  { to: '/arena', label: 'Battle Mode' },
  { to: '/bet', label: 'Bet' },
  { to: '/dashboard', label: 'My Tokens' },
]

export default function Header() {
  const { isAuthenticated, user, logout } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <header className="sticky top-0 z-50 bg-arena-surface border-b border-arena-border backdrop-blur-sm">
      <div className="container mx-auto px-4 max-w-[1400px] h-14 flex items-center gap-6">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2 font-mono font-bold text-arena-accent text-lg whitespace-nowrap">
          ⚔️ <span>Arena</span>
        </Link>

        {/* Navigation */}
        <nav className="hidden md:flex items-center gap-1 flex-1">
          {NAV_LINKS.map(({ to, label }) => (
            <Link
              key={to}
              to={to}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors
                ${location.pathname === to
                  ? 'bg-arena-card text-arena-text'
                  : 'text-arena-muted hover:text-arena-text hover:bg-arena-card'
                }`}
            >
              {label}
            </Link>
          ))}
        </nav>

        {/* Right side */}
        <div className="flex items-center gap-3 ml-auto">
          {isAuthenticated && user ? (
            <>
              {/* Token balance */}
              <div className="flex items-center gap-1.5 bg-arena-card border border-arena-border rounded px-3 py-1.5">
                <span className="text-arena-yellow text-sm">🪙</span>
                <span className="font-mono text-sm font-semibold text-arena-text">
                  {formatTokens(user.token_balance)}
                </span>
              </div>
              {/* User menu */}
              <div className="relative group">
                <button className="flex items-center gap-2 text-sm text-arena-muted hover:text-arena-text">
                  <span className="w-7 h-7 rounded-full bg-arena-accent/20 border border-arena-accent/40 flex items-center justify-center text-xs font-bold text-arena-accent">
                    {user.username.charAt(0).toUpperCase()}
                  </span>
                  <span className="hidden md:block">{user.username}</span>
                </button>
                <div className="absolute right-0 top-full mt-1 w-40 bg-arena-card border border-arena-border rounded shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
                  {user.is_admin && (
                    <Link to="/admin" className="block px-4 py-2 text-sm text-arena-muted hover:text-arena-text hover:bg-arena-surface">
                      Admin Panel
                    </Link>
                  )}
                  <button
                    onClick={() => { logout(); navigate('/') }}
                    className="block w-full text-left px-4 py-2 text-sm text-arena-red hover:bg-arena-surface"
                  >
                    Sign Out
                  </button>
                </div>
              </div>
            </>
          ) : (
            <Link
              to="/login"
              className="bg-arena-accent text-arena-bg text-sm font-semibold px-4 py-1.5 rounded hover:bg-arena-accent/90 transition-colors"
            >
              Sign In
            </Link>
          )}
        </div>
      </div>
    </header>
  )
}
