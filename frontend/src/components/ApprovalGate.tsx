import { useState } from "react"
import type { ApprovalPayload } from "../types"

interface ApprovalGateProps {
  payload: ApprovalPayload
  submitting: boolean
  onVerdict: (approved: boolean, comment?: string) => void
}

/** 人工审批面板：风控通过后、启用审批时展示，等待用户批准/驳回。 */
export default function ApprovalGate({ payload, submitting, onVerdict }: ApprovalGateProps) {
  const [comment, setComment] = useState("")

  return (
    <div className="af-card border-2 border-amber-200 bg-amber-50/60">
      <h3 className="mb-2 font-bold text-amber-900">🧑‍💼 等待人工审批</h3>
      <p className="text-sm text-amber-800">
        风控结论：<span className="font-semibold">{payload.decision}</span>
        {payload.reason && <span className="ml-1">— {payload.reason}</span>}
      </p>
      {typeof payload.rejections === "number" && payload.rejections > 0 && (
        <p className="mt-1 text-xs text-amber-700">已驳回 {payload.rejections} 次（超过上限将自动放行）</p>
      )}

      <textarea
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder="审批意见（驳回时建议填写，将反馈给策略层修订）"
        className="mt-3 w-full rounded-lg border border-amber-300 bg-white px-3 py-2 text-sm"
        rows={2}
        disabled={submitting}
      />

      <div className="mt-3 flex gap-2">
        <button
          type="button"
          disabled={submitting}
          onClick={() => onVerdict(true, comment || undefined)}
          className="rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white hover:bg-green-700 disabled:opacity-50"
        >
          通过
        </button>
        <button
          type="button"
          disabled={submitting}
          onClick={() => onVerdict(false, comment || undefined)}
          className="rounded-lg bg-red-500 px-4 py-2 text-sm font-semibold text-white hover:bg-red-600 disabled:opacity-50"
        >
          驳回并修订
        </button>
      </div>
    </div>
  )
}
