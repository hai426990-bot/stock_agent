import type { RiskAssessment as RiskAssessmentData } from "../types"

interface RiskAssessmentProps {
  data: RiskAssessmentData | string | unknown
}

const DECISION_STYLE: Record<string, string> = {
  通过: "bg-green-100 text-green-700",
  驳回: "bg-red-100 text-red-700",
  强制通过: "bg-yellow-100 text-yellow-700",
}

export default function RiskAssessment({ data }: RiskAssessmentProps) {
  if (!data) {
    return <div className="af-card py-10 text-center text-sm text-slate-400">暂无风控结论</div>
  }

  // Legacy string format (pre-structuring) — render as-is
  if (typeof data === "string") {
    return (
      <div className="af-card">
        <h3 className="mb-3 font-bold text-slate-900">🛡️ 风控结论</h3>
        <pre className="whitespace-pre-wrap rounded-lg bg-slate-50 p-4 text-sm text-slate-700">
          {data}
        </pre>
      </div>
    )
  }

  const decision = (data as RiskAssessmentData).decision || "未知"
  const reason = (data as RiskAssessmentData).reason || "未提供详细理由"
  const reviewCount = (data as RiskAssessmentData).review_count
  const reviewDate = (data as RiskAssessmentData).review_date

  return (
    <div className="af-card">
      <h3 className="mb-3 font-bold text-slate-900">🛡️ 风控结论</h3>
      <div className="space-y-3 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded px-2 py-1 font-semibold ${DECISION_STYLE[decision] || "bg-slate-100 text-slate-700"}`}>
            {decision}
          </span>
          {reviewCount != null && (
            <span className="text-xs text-slate-400">第 {reviewCount} 次审核</span>
          )}
          {reviewDate && <span className="text-xs text-slate-400">审核日期: {reviewDate}</span>}
        </div>
        <p className="whitespace-pre-wrap text-slate-700">{reason}</p>
      </div>
    </div>
  )
}
