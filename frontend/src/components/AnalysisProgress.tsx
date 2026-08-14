import type { NodeEvent } from "../types"

interface AnalysisProgressProps {
  events: NodeEvent[]
  stockName?: string
}

const nodeLabels: Record<string, string> = {
  supervisor: "调度器",
  news_node: "资讯分析",
  quant_node: "量化分析",
  telegraph_node: "电报分析",
  strategy_node: "策略生成",
  risk_node: "风险审核",
}

function NodeStep({ node, status }: { node?: string; status?: string }) {
  const label = node ? nodeLabels[node] || node : "未知"
  const isDone = status === "completed"
  const isError = status === "error"
  return (
    <div className="flex items-center gap-3">
      <div
        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
          isError
            ? "bg-red-100 text-red-600"
            : isDone
              ? "bg-green-100 text-green-600"
              : "bg-slate-100 text-slate-400"
        }`}
      >
        {isError ? "✕" : isDone ? "✓" : "○"}
      </div>
      <span
        className={`text-sm ${
          isError ? "text-red-600" : isDone ? "text-green-700" : "text-slate-400"
        }`}
      >
        {label}
        {isDone && " 完成"}
        {isError && " 失败"}
      </span>
    </div>
  )
}

export default function AnalysisProgress({ events, stockName }: AnalysisProgressProps) {
  const nodeEvents = events.filter((e) => e.event === "node")

  return (
    <div className="af-card space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-bold text-slate-900">🚀 AlphaFlow 协作中...</h3>
          {stockName && <p className="text-sm text-slate-500">正在分析 {stockName}</p>}
        </div>
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <span className="inline-block h-3 w-3 animate-pulse rounded-full bg-indigo-400" />
          运行中
        </div>
      </div>
      <div className="space-y-2">
        {nodeEvents.map((evt, i) => (
          <NodeStep key={i} node={evt.node} status={evt.status} />
        ))}
      </div>
    </div>
  )
}
