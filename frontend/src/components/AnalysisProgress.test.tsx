import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import AnalysisProgress from "./AnalysisProgress"
import type { NodeEvent } from "../types"

describe("AnalysisProgress", () => {
  const events: NodeEvent[] = [
    { event: "node", seq: 1, node: "supervisor", status: "completed" },
    { event: "node", seq: 2, node: "news_node", status: "completed" },
    { event: "node", seq: 3, node: "quant_node", status: "completed" },
    { event: "node", seq: 4, node: "telegraph_node", status: "completed" },
    { event: "node", seq: 5, node: "strategy_node", status: "completed" },
    { event: "node", seq: 6, node: "risk_node", status: "error", message: "驳回" },
    { event: "done", seq: 7, report_id: "r1" }, // 非 node 事件应被过滤
  ]

  it("渲染标的与全部节点进度（含失败态），过滤非 node 事件", () => {
    render(<AnalysisProgress events={events} stockName="贵州茅台" />)
    expect(screen.getByText("正在分析 贵州茅台")).toBeInTheDocument()
    expect(screen.getByText("资讯分析 完成")).toBeInTheDocument()
    expect(screen.getByText("量化分析 完成")).toBeInTheDocument()
    expect(screen.getByText("电报分析 完成")).toBeInTheDocument()
    expect(screen.getByText("策略生成 完成")).toBeInTheDocument()
    expect(screen.getByText("风险审核 失败")).toBeInTheDocument()
    // 未知节点回退为原始名称
    expect(screen.queryByText("done")).not.toBeInTheDocument()
  })

  it("未知节点名直接展示，无标的时不渲染标的行", () => {
    render(<AnalysisProgress events={[{ event: "node", seq: 1, node: "custom_node", status: "completed" }]} />)
    expect(screen.getByText("custom_node 完成")).toBeInTheDocument()
    expect(screen.queryByText(/正在分析/)).not.toBeInTheDocument()
  })
})
