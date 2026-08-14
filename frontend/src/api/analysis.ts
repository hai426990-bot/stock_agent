import client from "./client"
import type { AnalysisCreateResponse, AnalysisListItem, AnalysisDetail } from "../types"

export function createAnalysis(query: string): Promise<AnalysisCreateResponse> {
  return client.post("/analysis/", { query }).then((r) => r.data)
}

export function getAnalysisDetail(id: string): Promise<AnalysisDetail> {
  return client.get(`/analysis/${id}/`).then((r) => r.data)
}

export function listAnalyses(params?: {
  page?: number
  page_size?: number
  stock_code?: string
  status?: string
}): Promise<AnalysisListItem[]> {
  return client.get("/analysis/", { params }).then((r) => r.data)
}

export function deleteAnalysis(id: string): Promise<void> {
  return client.delete(`/analysis/${id}/`).then((r) => r.data)
}

export function buildStreamUrl(id: string, resumeFrom = 0): string {
  const base = import.meta.env.VITE_API_BASE || ""
  return `${base}/api/analysis/${id}/stream?resume_from=${resumeFrom}`
}
