import { useEffect, useRef, useCallback, useState } from "react"
import type { NodeEvent, ApprovalPayload } from "../types"

interface UseSSEOptions {
  onEvent?: (event: NodeEvent) => void
  onDone?: (reportId: string) => void
  onError?: (message: string) => void
  onApproval?: (payload: ApprovalPayload) => void
  onApprovalResumed?: (verdict: { approved: boolean; comment?: string }) => void
  enabled?: boolean
}

interface UseSSEReturn {
  connected: boolean
  error: string | null
  close: () => void
}

export function useSSE(url: string | null, options: UseSSEOptions = {}): UseSSEReturn {
  const { onEvent, onDone, onError, onApproval, onApprovalResumed, enabled = true } = options
  const esRef = useRef<EventSource | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // seq of the last event received for the CURRENT stream. Must NOT carry over
  // to a different job: the backend renumbers seq from 1 per report, so a stale
  // resume_from would swallow the new job's early progress events.
  const lastEventIdRef = useRef(0)
  const streamUrlRef = useRef<string | null>(null)

  const close = useCallback(() => {
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
      setConnected(false)
    }
  }, [])

  useEffect(() => {
    if (!url || !enabled) return

    // New job (different stream URL) -> start from seq 0
    if (streamUrlRef.current !== url) {
      streamUrlRef.current = url
      lastEventIdRef.current = 0
    }

    const resumeFrom = lastEventIdRef.current
    const fullUrl =
      resumeFrom > 0
        ? `${url}${url.includes("?") ? "&" : "?"}resume_from=${resumeFrom}`
        : url
    const es = new EventSource(fullUrl)
    esRef.current = es
    setError(null)

    es.onopen = () => {
      // close() 后浏览器不再派发事件，但防御性守卫避免竞态下误报已连接
      if (es.readyState !== EventSource.CLOSED) setConnected(true)
    }

    es.addEventListener("node", (e: MessageEvent) => {
      const data: NodeEvent = JSON.parse(e.data)
      if (data.seq) lastEventIdRef.current = data.seq
      onEvent?.(data)
    })

    es.addEventListener("done", (e: MessageEvent) => {
      const data: NodeEvent = JSON.parse(e.data)
      onDone?.(data.report_id || "")
      close()
    })

    es.addEventListener("approval", (e: MessageEvent) => {
      const data: NodeEvent = JSON.parse(e.data)
      if (data.payload) onApproval?.(data.payload)
    })

    es.addEventListener("approval_resumed", (e: MessageEvent) => {
      const data: NodeEvent = JSON.parse(e.data)
      if (data.verdict) onApprovalResumed?.(data.verdict)
    })

    es.addEventListener("error", (e: MessageEvent) => {
      let msg = "连接异常"
      try {
        const data: NodeEvent = JSON.parse(e.data)
        msg = data.message || msg
      } catch { /* ignore */ }
      setError(msg)
      onError?.(msg)
    })

    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) {
        setConnected(false)
      }
    }

    return () => {
      es.close()
      setConnected(false)
    }
  }, [url, enabled, onEvent, onDone, onError, onApproval, onApprovalResumed, close])

  return { connected, error, close }
}
