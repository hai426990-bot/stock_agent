import { useState, useCallback } from "react"
import { createAnalysis, getAnalysisDetail, submitApproval } from "../api/analysis"
import type { AnalysisDetail, NodeEvent, AnalysisStatus, ApprovalPayload } from "../types"

interface UseAnalysisReturn {
  status: AnalysisStatus | "idle"
  jobId: string | null
  stockInfo: { code: string; name: string } | null
  progress: NodeEvent[]
  detail: AnalysisDetail | null
  error: string | null
  approvalRequest: ApprovalPayload | null
  approvalSubmitting: boolean
  startAnalysis: (query: string) => Promise<string | null>
  handleNodeEvent: (event: NodeEvent) => void
  handleDone: (reportId: string) => void
  handleError: (message: string) => void
  handleApproval: (payload: ApprovalPayload) => void
  handleApprovalResumed: () => void
  submitVerdict: (approved: boolean, comment?: string) => Promise<boolean>
  reset: () => void
}

export function useAnalysis(): UseAnalysisReturn {
  const [status, setStatus] = useState<AnalysisStatus | "idle">("idle")
  const [jobId, setJobId] = useState<string | null>(null)
  const [stockInfo, setStockInfo] = useState<{ code: string; name: string } | null>(null)
  const [progress, setProgress] = useState<NodeEvent[]>([])
  const [detail, setDetail] = useState<AnalysisDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [approvalRequest, setApprovalRequest] = useState<ApprovalPayload | null>(null)
  const [approvalSubmitting, setApprovalSubmitting] = useState(false)

  const startAnalysis = useCallback(async (query: string): Promise<string | null> => {
    setStatus("pending")
    setProgress([])
    setDetail(null)
    setError(null)
    setApprovalRequest(null)
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
    setApprovalRequest(null)
    try {
      const detailData = await getAnalysisDetail(reportId)
      setDetail(detailData)
    } catch { /* detail loaded later via fetch */ }
  }, [])

  const handleError = useCallback((message: string) => {
    setError(message)
    setStatus("failed")
    setApprovalRequest(null)
  }, [])

  const handleApproval = useCallback((payload: ApprovalPayload) => {
    setApprovalRequest(payload)
    setStatus("awaiting_approval")
  }, [])

  const handleApprovalResumed = useCallback(() => {
    setApprovalRequest(null)
    setStatus("running")
  }, [])

  const submitVerdict = useCallback(async (approved: boolean, comment?: string): Promise<boolean> => {
    if (!jobId) return false
    setApprovalSubmitting(true)
    try {
      await submitApproval(jobId, { approved, comment })
      // 等待 approval_resumed 事件把状态切回 running；这里先清掉审批面板
      setApprovalRequest(null)
      setStatus("running")
      return true
    } catch (e) {
      const msg = e instanceof Error ? e.message : "提交审批失败"
      setError(msg)
      return false
    } finally {
      setApprovalSubmitting(false)
    }
  }, [jobId])

  const reset = useCallback(() => {
    setStatus("idle")
    setJobId(null)
    setProgress([])
    setDetail(null)
    setError(null)
    setApprovalRequest(null)
    setApprovalSubmitting(false)
  }, [])

  return {
    status, jobId, stockInfo, progress, detail, error,
    approvalRequest, approvalSubmitting,
    startAnalysis, handleNodeEvent, handleDone, handleError,
    handleApproval, handleApprovalResumed, submitVerdict, reset,
  }
}
