/**
 * Zustand auth store — persists JWT token and user data to localStorage.
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User, AuthResponse } from '@/types'

interface AuthState {
  token: string | null
  user: User | null
  isAuthenticated: boolean
  setAuth: (response: AuthResponse, userProfile: User) => void
  updateBalance: (newBalance: number) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isAuthenticated: false,

      setAuth: (response, userProfile) => {
        set({
          token: response.access_token,
          user: userProfile,
          isAuthenticated: true,
        })
      },

      updateBalance: (newBalance) => {
        set((state) => ({
          user: state.user ? { ...state.user, token_balance: newBalance } : null,
        }))
      },

      logout: () => {
        set({ token: null, user: null, isAuthenticated: false })
      },
    }),
    {
      name: 'arena-auth',
      partialize: (state) => ({ token: state.token, user: state.user }),
    },
  ),
)
