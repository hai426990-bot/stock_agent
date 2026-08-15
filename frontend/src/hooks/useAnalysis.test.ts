import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, act, waitFor } from "@testing-library/react"
import { useAnalysis } from "./useAnalysis"
import { createAnalysis, getAnalysisDetail } from "../api/analysis"

vi.mock("../api/analysis", () => ({
  createAnalysis: vi.fn(),
  getAnalysisDetail: vi.fn(),
  listAnalyses: vi.fn(),
  deleteAnalysis: vi.fn(),
  buildStreamUrl: vi.fn(),
}))

const mockCreate = vi.mocked(createAnalysis)
const mockDetail = vi.mocked(getAnalysisDetail)

const CREATE_RESP = {
  job_id: "job-1",
  status: "pending",
  stock_code: "600519",
  stock_name: "贵州茅台",
  is_sector: false,
}

beforeEach(() => {
  mockCreate.mockReset()
  mockDetail.mockReset()
})

describe("useAnalysis", () => {
  it("startAnalysis 成功后进入 running 并记录 jobId", async () => {
    mockCreate.mockResolvedValue(CREATE_RESP)
    const { result } = renderHook(() => useAnalysis())

    let jobId: string | null = null
    await act(async () => {
      jobId = await result.current.startAnalysis("600519")
    })

    expect(jobId).toBe("job-1")
    expect(result.current.status).toBe("running")
    expect(result.current.jobId).toBe("job-1")
    expect(result.current.stockInfo).toEqual({ code: "600519", name: "贵州茅台" })
    expect(mockCreate).toHaveBeenCalledWith("600519")
  })

  it("startAnalysis 失败后进入 failed 并返回 null", async () => {
    mockCreate.mockRejectedValue(new Error("并发分析任务已达上限"))
    const { result } = renderHook(() => useAnalysis())

    let jobId: string | null = "x"
    await act(async () => {
      jobId = await result.current.startAnalysis("600519")
    })

    expect(jobId).toBeNull()
    expect(result.current.status).toBe("failed")
    expect(result.current.error).toBe("并发分析任务已达上限")
  })

  it("handleNodeEvent 追加进度事件", () => {
    const { result } = renderHook(() => useAnalysis())
    act(() => {
      result.current.handleNodeEvent({ event: "node", seq: 1, node: "news_node", status: "completed" })
      result.current.handleNodeEvent({ event: "node", seq: 2, node: "risk_node", status: "error", message: "x" })
    })
    expect(result.current.progress).toHaveLength(2)
    expect(result.current.progress[1].status).toBe("error")
  })

  it("handleDone 拉取详情并进入 completed", async () => {
    const detail = { id: "job-1", status: "completed" }
    mockDetail.mockResolvedValue(detail as never)
    const { result } = renderHook(() => useAnalysis())

    await act(async () => {
      await result.current.handleDone("job-1")
    })

    expect(result.current.status).toBe("completed")
    expect(mockDetail).toHaveBeenCalledWith("job-1")
    await waitFor(() => expect(result.current.detail).toEqual(detail))
  })

  it("handleError 进入 failed", () => {
    const { result } = renderHook(() => useAnalysis())
    act(() => {
      result.current.handleError("worker 已退出")
    })
    expect(result.current.status).toBe("failed")
    expect(result.current.error).toBe("worker 已退出")
  })

  it("reset 清空全部状态", () => {
    mockCreate.mockResolvedValue(CREATE_RESP)
    const { result } = renderHook(() => useAnalysis())
    act(() => {
      result.current.handleNodeEvent({ event: "node", seq: 1, node: "supervisor", status: "completed" })
      result.current.reset()
    })
    expect(result.current.status).toBe("idle")
    expect(result.current.jobId).toBeNull()
    expect(result.current.progress).toEqual([])
    expect(result.current.detail).toBeNull()
  })
})
