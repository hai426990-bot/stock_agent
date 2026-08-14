import type { BacktestCandidate } from "../types"

interface BacktestCandidatesProps {
  candidates?: BacktestCandidate[]
}

function sharpeBadge(sharpe: number) {
  if (sharpe >= 1.5) return { label: `Sharpe ${sharpe.toFixed(2)}`, bg: "bg-green-100 text-green-800" }
  if (sharpe >= 1.0) return { label: `Sharpe ${sharpe.toFixed(2)}`, bg: "bg-teal-100 text-teal-700" }
  if (sharpe >= 0.5) return { label: `Sharpe ${sharpe.toFixed(2)}`, bg: "bg-blue-100 text-blue-700" }
  if (sharpe >= 0.0) return { label: `Sharpe ${sharpe.toFixed(2)}`, bg: "bg-yellow-100 text-yellow-800" }
  return { label: `Sharpe ${sharpe.toFixed(2)}`, bg: "bg-red-100 text-red-800" }
}

function mddBadge(mdd: number) {
  if (mdd >= -0.12) return { label: `MDD ${(mdd * 100).toFixed(1)}%`, bg: "bg-green-100 text-green-800" }
  if (mdd >= -0.25) return { label: `MDD ${(mdd * 100).toFixed(1)}%`, bg: "bg-yellow-100 text-yellow-800" }
  return { label: `MDD ${(mdd * 100).toFixed(1)}%`, bg: "bg-red-100 text-red-800" }
}

function CandidateCard({ candidate }: { candidate: BacktestCandidate }) {
  const m = candidate.metrics
  const sBadge = sharpeBadge(m.sharpe)
  const dBadge = mddBadge(m.max_drawdown)

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center gap-2">
        <span className="font-semibold text-slate-900">{candidate.label}</span>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${sBadge.bg}`}>
          {sBadge.label}
        </span>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${dBadge.bg}`}>
          {dBadge.label}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-4 text-center text-sm">
        <div>
          <div className="text-lg font-bold text-slate-900">{(m.cagr * 100).toFixed(2)}%</div>
          <div className="text-xs text-slate-500">CAGR</div>
        </div>
        <div>
          <div className="text-lg font-bold text-slate-900">{(m.win_rate * 100).toFixed(2)}%</div>
          <div className="text-xs text-slate-500">胜率</div>
        </div>
        <div>
          <div className="text-lg font-bold text-slate-900">{(m.max_drawdown * 100).toFixed(2)}%</div>
          <div className="text-xs text-slate-500">MDD</div>
        </div>
      </div>
    </div>
  )
}

export default function BacktestCandidates({ candidates }: BacktestCandidatesProps) {
  if (!candidates || candidates.length === 0) {
    return <div className="af-card py-10 text-center text-sm text-slate-400">暂无回测策略数据</div>
  }

  return (
    <div className="space-y-3">
      <h3 className="font-bold text-slate-900">📊 回测策略</h3>
      <div className="grid gap-3 md:grid-cols-2">
        {candidates.slice(0, 4).map((c, i) => (
          <CandidateCard key={i} candidate={c} />
        ))}
      </div>
    </div>
  )
}
