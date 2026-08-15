import { useCallback, useEffect } from "react"
import { useQuery } from "@tanstack/react-query"
import AnalysisForm from "../components/AnalysisForm"
import AnalysisProgress from "../components/AnalysisProgress"
import ApprovalGate from "../components/ApprovalGate"
import ReportViewer from "../components/ReportViewer"
import RiskAssessment from "../components/RiskAssessment"
import BacktestCandidates from "../components/BacktestCandidates"
import { useAnalysis } from "../hooks/useAnalysis"
import { useSSE } from "../hooks/useSSE"
import { buildStreamUrl, listAnalyses } from "../api/analysis"

export default function Analysis() {
  const analysis = useAnalysis()

  const handleSubmit = useCallback(
    async (query: string) => {
      await analysis.startAnalysis(query)
    },
    [analysis.startAnalysis],
  )

  const { error: sseError } = useSSE(
    analysis.jobId ? buildStreamUrl(analysis.jobId) : null,
    {
      onEvent: analysis.handleNodeEvent,
      onDone: analysis.handleDone,
      onError: analysis.handleError,
      onApproval: analysis.handleApproval,
      onApprovalResumed: analysis.handleApprovalResumed,
      enabled: analysis.status === "running" || analysis.status === "awaiting_approval",
    },
  )

  useEffect(() => {
    if (sseError && analysis.status === "running") {
      analysis.handleError(sseError)
    }
  }, [sseError, analysis.status, analysis.handleError])

  const historyQuery = useQuery({
    queryKey: ["analysis-list"],
    queryFn: () => listAnalyses({ page_size: 10 }),
    // The history sidebar only renders when idle; don't poll while an
    // analysis is running or after it finished.
    refetchInterval: analysis.status === "idle" ? 30_000 : false,
  })

  const detail = analysis.detail
  const finalState = detail?.final_state || {}
  const quantData = finalState.quant_data || {}
  const candidates = quantData.backtest_candidates

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
      <div className="space-y-6">
        <div>
          <h1 className="text-xl font-extrabold text-slate-900">智能分析</h1>
          <p className="mt-1 text-sm text-slate-500">
            输入股票代码或名称，启动多智能体协作分析
          </p>
        </div>

        <AnalysisForm
          onSubmit={handleSubmit}
          disabled={analysis.status === "running" || analysis.status === "pending"}
          loading={analysis.status === "pending"}
        />

        {analysis.error && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {analysis.error}
          </div>
        )}

        {(analysis.status === "running" || analysis.status === "pending") && (
          <AnalysisProgress
            events={analysis.progress}
            stockName={analysis.stockInfo?.name}
          />
        )}

        {analysis.status === "awaiting_approval" && analysis.approvalRequest && (
          <>
            <AnalysisProgress
              events={analysis.progress}
              stockName={analysis.stockInfo?.name}
            />
            <ApprovalGate
              payload={analysis.approvalRequest}
              submitting={analysis.approvalSubmitting}
              onVerdict={analysis.submitVerdict}
            />
          </>
        )}

        {analysis.status === "completed" && detail && (
          <>
            <div className="flex items-center gap-2 text-sm text-green-600">
              <span className="inline-block h-2 w-2 rounded-full bg-green-500" />
              分析完成
            </div>

            {finalState.strategy_report && (
              <ReportViewer
                content={finalState.strategy_report}
                stockName={finalState.stock_name}
                stockCode={finalState.stock_code}
              />
            )}

            {finalState.risk_assessment && (
              <RiskAssessment data={finalState.risk_assessment} />
            )}

            {candidates && candidates.length > 0 && (
              <BacktestCandidates candidates={candidates} />
            )}
          </>
        )}

        {analysis.status === "failed" && !analysis.error && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            分析失败
          </div>
        )}
      </div>

      <div className="space-y-4">
        {analysis.status === "idle" && (
          <div className="af-card">
            <h3 className="mb-3 font-bold text-slate-900">🕒 最近分析</h3>
            {historyQuery.data && historyQuery.data.length > 0 ? (
              <div className="space-y-2">
                {historyQuery.data.map((item) => (
                  <div key={item.id} className="text-sm">
                    <div className="font-medium text-slate-800">{item.stock_name} ({item.stock_code})</div>
                    <div className="flex items-center gap-2 text-xs text-slate-400">
                      <span>{new Date(item.created_at).toLocaleString("zh-CN")}</span>
                      <span className={`rounded px-1.5 py-0.5 ${
                        item.status === "completed" ? "bg-green-100 text-green-700"
                          : item.status === "failed" ? "bg-red-100 text-red-700"
                            : "bg-yellow-100 text-yellow-700"
                      }`}>{item.status}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-400">暂无分析记录</p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
