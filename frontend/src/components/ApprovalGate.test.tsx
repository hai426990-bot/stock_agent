import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import ApprovalGate from "./ApprovalGate"

describe("ApprovalGate", () => {
  it("展示风控结论与驳回次数，通过/驳回按钮回调正确", () => {
    const onVerdict = vi.fn()
    render(
      <ApprovalGate
        payload={{ decision: "通过", reason: "逻辑自洽", review_count: 1, rejections: 1 }}
        submitting={false}
        onVerdict={onVerdict}
      />,
    )
    expect(screen.getByText(/等待人工审批/)).toBeInTheDocument()
    expect(screen.getByText(/逻辑自洽/)).toBeInTheDocument()
    expect(screen.getByText(/已驳回 1 次/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "通过" }))
    expect(onVerdict).toHaveBeenCalledWith(true, undefined)
  })

  it("驳回时把审批意见传给 onVerdict", () => {
    const onVerdict = vi.fn()
    render(
      <ApprovalGate
        payload={{ decision: "通过", reason: "ok" }}
        submitting={false}
        onVerdict={onVerdict}
      />,
    )
    fireEvent.change(screen.getByPlaceholderText(/审批意见/), {
      target: { value: "风险提示不足" },
    })
    fireEvent.click(screen.getByRole("button", { name: "驳回并修订" }))
    expect(onVerdict).toHaveBeenCalledWith(false, "风险提示不足")
  })

  it("提交中禁用按钮", () => {
    render(
      <ApprovalGate payload={{ decision: "通过", reason: "ok" }} submitting onVerdict={vi.fn()} />,
    )
    expect(screen.getByRole("button", { name: "通过" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "驳回并修订" })).toBeDisabled()
  })
})
