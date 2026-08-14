import { Link } from "react-router-dom"
import MarketDashboard from "../components/MarketDashboard"
import ConfigPanel from "../components/ConfigPanel"

export default function Dashboard() {
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
      <div className="space-y-6">
        <div className="af-hero flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
              AlphaFlow 智能投资决策系统
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              基于 LangGraph 的多智能体协作 A 股决策平台
            </p>
          </div>
          <Link
            to="/analysis"
            className="rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700"
          >
            开始分析 →
          </Link>
        </div>
        <MarketDashboard />
      </div>
      <div className="space-y-4">
        <ConfigPanel />
      </div>
    </div>
  )
}
