import { Outlet } from 'react-router-dom'
import Header from './Header'
import LiveTickerBar from '@/components/arena/LiveTickerBar'

export default function Layout() {
  return (
    <div className="min-h-screen bg-arena-bg text-arena-text flex flex-col">
      <Header />
      {/* Live trade ticker at top */}
      <LiveTickerBar />
      <main className="flex-1 container mx-auto px-4 py-6 max-w-[1400px]">
        <Outlet />
      </main>
      <footer className="border-t border-arena-border py-4 px-6 text-center text-arena-muted text-xs">
        AI Trading Agent Arena — Paper trading only. Arena Tokens have no monetary value.
        &nbsp;|&nbsp;
        Based on <a href="https://github.com/HKUDS/AI-Trader" className="text-arena-accent hover:underline" target="_blank" rel="noopener">AI-Traderv2</a>
      </footer>
    </div>
  )
}
