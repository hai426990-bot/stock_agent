import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, act } from "@testing-library/react"
import { useSSE } from "./useSSE"

/**
 * jsdom 没有 EventSource 实现 —— 用最小 fake 替身：
 * 记录创建的 URL / 关闭状态，并允许测试手动派发事件。
 */
class FakeEventSource {
  static instances: FakeEventSource[] = []
  static CONNECTING = 0
  static OPEN = 1
  static CLOSED = 2

  url: string
  readyState = FakeEventSource.CONNECTING
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  private listeners: Record<string, Array<(e: { data: string }) => void>> = {}

  constructor(url: string) {
    this.url = url
    FakeEventSource.instances.push(this)
  }

  addEventListener(type: string, cb: (e: { data: string }) => void) {
    ;(this.listeners[type] ||= []).push(cb)
  }

  removeEventListener() {}

  close() {
    this.readyState = FakeEventSource.CLOSED
  }

  emit(type: string, data: unknown) {
    for (const cb of this.listeners[type] || []) {
      cb({ data: JSON.stringify(data) })
    }
  }
}

beforeEach(() => {
  FakeEventSource.instances = []
  vi.stubGlobal("EventSource", FakeEventSource)
})

describe("useSSE", () => {
  it("创建 EventSource 并解析 node 事件", () => {
    const onEvent = vi.fn()
    renderHook(() =>
      useSSE("http://x/api/analysis/abc/stream", { onEvent }),
    )
    expect(FakeEventSource.instances).toHaveLength(1)
    expect(FakeEventSource.instances[0].url).toBe("http://x/api/analysis/abc/stream")

    act(() => {
      FakeEventSource.instances[0].emit("node", { seq: 1, node: "news_node", status: "completed" })
    })
    expect(onEvent).toHaveBeenCalledWith({ seq: 1, node: "news_node", status: "completed" })
  })

  it("done 事件触发 onDone 并关闭连接", () => {
    const onDone = vi.fn()
    const { result } = renderHook(() => useSSE("http://x/s", { onDone }))
    act(() => {
      FakeEventSource.instances[0].emit("done", { report_id: "r1" })
    })
    expect(onDone).toHaveBeenCalledWith("r1")
    expect(FakeEventSource.instances[0].readyState).toBe(FakeEventSource.CLOSED)
    // 关闭后 onopen 不再置 connected
    act(() => {
      FakeEventSource.instances[0].onopen?.()
    })
    expect(result.current.connected).toBe(false)
  })

  it("error 事件触发 onError 并携带 message", () => {
    const onError = vi.fn()
    renderHook(() => useSSE("http://x/s", { onError }))
    act(() => {
      FakeEventSource.instances[0].emit("error", { node: "orchestrator", message: "boom" })
    })
    expect(onError).toHaveBeenCalledWith("boom")
  })

  it("approval 事件触发 onApproval 携带 payload", () => {
    const onApproval = vi.fn()
    renderHook(() => useSSE("http://x/s", { onApproval }))
    act(() => {
      FakeEventSource.instances[0].emit("approval", {
        seq: 8,
        payload: { decision: "通过", reason: "逻辑自洽", review_count: 1 },
      })
    })
    expect(onApproval).toHaveBeenCalledWith({ decision: "通过", reason: "逻辑自洽", review_count: 1 })
  })

  it("approval_resumed 事件触发 onApprovalResumed 携带 verdict", () => {
    const onApprovalResumed = vi.fn()
    renderHook(() => useSSE("http://x/s", { onApprovalResumed }))
    act(() => {
      FakeEventSource.instances[0].emit("approval_resumed", {
        seq: 9,
        verdict: { approved: false, comment: "风险提示不足" },
      })
    })
    expect(onApprovalResumed).toHaveBeenCalledWith({ approved: false, comment: "风险提示不足" })
  })

  it("同一 job 断线重连时携带 resume_from=lastSeq", () => {
    const onEvent = vi.fn()
    const handlers = { onEvent } // 稳定引用，避免 effect 因回调变化重启
    const { rerender } = renderHook(
      ({ enabled }) => useSSE("http://x/s", { ...handlers, enabled }),
      { initialProps: { enabled: true } },
    )

    act(() => {
      FakeEventSource.instances[0].emit("node", { seq: 3, node: "quant_node", status: "completed" })
    })

    // 断开（enabled=false 触发清理）后重连同一 URL
    rerender({ enabled: false })
    rerender({ enabled: true })

    expect(FakeEventSource.instances).toHaveLength(2)
    expect(FakeEventSource.instances[1].url).toBe("http://x/s?resume_from=3")
  })

  it("不同 job 的 URL 不携带旧 resume_from", () => {
    const onEvent = vi.fn()
    const { rerender } = renderHook(
      ({ url }) => useSSE(url, { onEvent }),
      { initialProps: { url: "http://x/job-a" } },
    )
    act(() => {
      FakeEventSource.instances[0].emit("node", { seq: 5, node: "risk_node", status: "completed" })
    })
    rerender({ url: "http://x/job-b" })
    expect(FakeEventSource.instances[1].url).toBe("http://x/job-b")
  })
})
