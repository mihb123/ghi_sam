import * as React from "react"

import { fetchBoard, type Board } from "@/lib/api"
import { DEFAULT_REFRESH_INTERVAL } from "@/lib/settings"

export type BoardState = {
  board: Board | null
  error: Error | null
  loading: boolean
  reload: () => void
}

export function useBoard(
  token: string | null,
  refreshIntervalSec: number = DEFAULT_REFRESH_INTERVAL
): BoardState {
  const [board, setBoard] = React.useState<Board | null>(null)
  const [error, setError] = React.useState<Error | null>(null)
  const [loading, setLoading] = React.useState(Boolean(token))
  const inflight = React.useRef<AbortController | null>(null)

  const load = React.useCallback(async () => {
    if (!token) {
      return
    }
    inflight.current?.abort()
    const controller = new AbortController()
    inflight.current = controller
    setLoading(true)

    try {
      const next = await fetchBoard(token, controller.signal)
      setBoard(next)
      setError(null)
    } catch (cause) {
      if (controller.signal.aborted) {
        return
      }
      // Giu lai ban cu tren man hinh: mat song giua ban van xem duoc so diem gan nhat.
      setError(cause instanceof Error ? cause : new Error(String(cause)))
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false)
      }
    }
  }, [token])

  React.useEffect(() => {
    // setLoading(true) o day khong tao render thua vi state khoi tao da la true; rule
    // set-state-in-effect khong nhin thay dieu do nen phai tat rieng dong nay.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load()

    if (refreshIntervalSec <= 0) {
      return () => {
        inflight.current?.abort()
      }
    }

    // Chi goi khi tab dang mo: khoa man hinh thi khong ton pin va 4G.
    const tick = () => {
      if (document.visibilityState === "visible") {
        void load()
      }
    }
    const timer = window.setInterval(tick, refreshIntervalSec * 1000)
    document.addEventListener("visibilitychange", tick)
    window.addEventListener("online", tick)

    return () => {
      window.clearInterval(timer)
      document.removeEventListener("visibilitychange", tick)
      window.removeEventListener("online", tick)
      inflight.current?.abort()
    }
  }, [load, refreshIntervalSec])

  return { board, error, loading, reload: load }
}

