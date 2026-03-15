/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: [
    './index.html',
    './src/**/*.{ts,tsx,js,jsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Dark trading terminal palette (TradingView/ai4trade inspired)
        arena: {
          bg: '#0d1117',
          surface: '#161b22',
          card: '#1c2128',
          border: '#30363d',
          text: '#e6edf3',
          muted: '#7d8590',
          accent: '#58a6ff',
          green: '#3fb950',
          red: '#f85149',
          yellow: '#d29922',
          purple: '#bc8cff',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'ticker': 'ticker 20s linear infinite',
        'pulse-green': 'pulse-green 1s ease-in-out',
        'pulse-red': 'pulse-red 1s ease-in-out',
      },
      keyframes: {
        ticker: {
          '0%': { transform: 'translateX(100%)' },
          '100%': { transform: 'translateX(-100%)' },
        },
        'pulse-green': {
          '0%, 100%': { backgroundColor: 'transparent' },
          '50%': { backgroundColor: 'rgba(63, 185, 80, 0.15)' },
        },
        'pulse-red': {
          '0%, 100%': { backgroundColor: 'transparent' },
          '50%': { backgroundColor: 'rgba(248, 81, 73, 0.15)' },
        },
      },
    },
  },
  plugins: [],
}
