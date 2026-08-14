import { useState, useCallback } from "react"
import { createAnalysis, getAnalysisDetail } from "../api/analysis"
import type { AnalysisDetail, NodeEvent, AnalysisStatus } from "../types"

interface UseAnalysisReturn {
  status: AnalysisStatus | "idle"
  jobId: string | null
  stockInfo: { code: string; name: string } | null
  progress: NodeEvent[]
  detail: AnalysisDetail | null
  error: string | null
  startAnalysis: (query: string) => Promise<string | null>
  handleNodeEvent: (event: NodeEvent) => void
  handleDone: (reportId: string) => void
  handleError: (message: string) => void
  reset: () => void
}

export function useAnalysis(): UseAnalysisReturn {
  const [status, setStatus] = useState<AnalysisStatus | "idle">("idle")
  const [jobId, setJobId] = useState<string | null>(null)
  const [stockInfo, setStockInfo] = useState<{ code: string; name: string } | null>(null)
  const [progress, setProgress] = useState<NodeEvent[]>([])
  const [detail, setDetail] = useState<AnalysisDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  const startAnalysis = useCallback(async (query: string): Promise<string | null> => {
    setStatus("pending")
    setProgress([])
    setDetail(null)
    setError(null)
    try {
      const resp = await createAnalysis(query)
      setJobId(resp.job_id)
      setStockInfo({ code: resp.stock_code, name: resp.stock_name })
      setStatus("running")
      return resp.job_id
    } catch (e) {
      const msg = e instanceof Error ? e.message : "创建分析失败"
      setError(msg)
      setStatus("failed")
      return null
    }
  }, [])

  const handleNodeEvent = useCallback((event: NodeEvent) => {
    setProgress((prev) => [...prev, event])
  }, [])

  const handleDone = useCallback(async (reportId: string) => {
    setStatus("completed")
    try {
      const detailData = await getAnalysisDetail(reportId)
      setDetail(detailData)
    } catch { /* detail loaded later via fetch */ }
  }, [])

  const handleError = useCallback((message: string) => {
    setError(message)
    setStatus("failed")
  }, [])

  const reset = useCallback(() => {
    setStatus("idle")
    setJobId(null)
    setProgress([])
    setDetail(null)
    setError(null)
  }, [])

  return {
    status, jobId, stockInfo, progress, detail, error,
    startAnalysis, handleNodeEvent, handleDone, handleError, reset,
  }
}
