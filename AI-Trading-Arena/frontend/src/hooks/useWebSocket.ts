/**
 * WebSocket hooks for real-time leaderboard and trade stream.
 */
import { useEffect, useRef, useCallback, useState } from 'react'
import type { Agent, LiveTrade } from '@/types'

function getWsBase(): string {
  const envUrl = (import.meta as { env?: { VITE_WS_URL?: string } }).env?.VITE_WS_URL
  if (envUrl) return envUrl.replace(/^http/, 'ws')
  return `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`
}

interface UseWebSocketOptions {
  onMessage: (data: unknown) => void
  reconnectInterval?: number
}

function useWebSocket(url: string, options: UseWebSocketOptions) {
  const ws = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>()
  const { onMessage, reconnectInterval = 3000 } = options

  const connect = useCallback(() => {
    try {
      ws.current = new WebSocket(url)

      ws.current.onopen = () => {
        // Send ping every 25s to keep connection alive
        const ping = setInterval(() => {
          if (ws.current?.readyState === WebSocket.OPEN) {
            ws.current.send('ping')
          }
        }, 25_000)
        ws.current!.onclose = () => clearInterval(ping)
      }

      ws.current.onmessage = (event) => {
        if (event.data === 'pong') return
        try {
          const data = JSON.parse(event.data)
          onMessage(data)
        } catch (e) {
          // ignore parse errors
        }
      }

      ws.current.onerror = () => {
        ws.current?.close()
      }

      ws.current.onclose = () => {
        reconnectTimer.current = setTimeout(connect, reconnectInterval)
      }
    } catch (e) {
      reconnectTimer.current = setTimeout(connect, reconnectInterval)
    }
  }, [url, onMessage, reconnectInterval])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      ws.current?.close()
    }
  }, [connect])
}


/** Hook for live leaderboard updates */
export function useLeaderboardWs(onUpdate: (agents: Agent[]) => void) {
  const url = `${getWsBase()}/ws/leaderboard`
  useWebSocket(url, {
    onMessage: (data) => {
      const msg = data as { type?: string; data?: Agent[] }
      if (msg.type === 'leaderboard_update' && msg.data) {
        onUpdate(msg.data)
      }
    },
  })
}


/** Hook for live trade stream */
export function useTradesWs(onTrade: (trade: LiveTrade) => void) {
  const url = `${getWsBase()}/ws/trades`
  useWebSocket(url, {
    onMessage: (data) => {
      onTrade(data as LiveTrade)
    },
  })
}
