import * as React from "react"

import { fetchStats, type Stats } from "@/lib/api"

export type StatsState = {
  stats: Stats | null
  error: Error | null
  loading: boolean
  reload: () => void
}

/** Cung khuon voi use-board: huy request cu, chi poll khi tab dang mo, mat song thi giu so cu. */
export function useStats(
  token: string | null,
  refreshIntervalSec = 60
): StatsState {
  const [stats, setStats] = React.useState<Stats | null>(null)
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
      const next = await fetchStats(token, controller.signal)
      setStats(next)
      setError(null)
    } catch (cause) {
      if (controller.signal.aborted) {
        return
      }
      setError(cause instanceof Error ? cause : new Error(String(cause)))
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false)
      }
    }
  }, [token])

  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load()

    if (refreshIntervalSec <= 0) {
      return () => {
        inflight.current?.abort()
      }
    }

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

  return { stats, error, loading, reload: load }
}
