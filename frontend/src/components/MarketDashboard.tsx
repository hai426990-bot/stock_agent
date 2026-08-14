import { useQuery } from "@tanstack/react-query"
import { getMarketIndices, getHotSectors, getMarketSentiment } from "../api/market"
import type { HotSector, MarketIndex } from "../types"

function IndexCard({ index }: { index: MarketIndex }) {
  const isUp = index.change_pct >= 0
  return (
    <div className="af-card flex flex-col items-center p-3 text-center">
      <div className="text-xs text-slate-500">{index.name}</div>
      <div className="mt-1 text-lg font-bold text-slate-900">{index.price}</div>
      <div className={`text-sm font-medium ${isUp ? "text-green-600" : "text-red-500"}`}>
        {isUp ? "+" : ""}{index.change_pct.toFixed(2)}%
      </div>
    </div>
  )
}

function SentimentBar({ up, down }: { up: number; down: number }) {
  const total = up + down || 1
  const upPct = (up / total) * 100
  return (
    <div className="flex h-6 w-full overflow-hidden rounded-full bg-slate-200">
      <div className="bg-red-400 transition-all" style={{ width: `${upPct}%` }} />
      <div className="bg-green-400 transition-all" style={{ width: `${100 - upPct}%` }} />
    </div>
  )
}

function SectorTable({ sectors }: { sectors: HotSector[] }) {
  if (!sectors.length) return <div className="text-sm text-slate-400">暂无数据</div>
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-slate-500">
            <th className="pb-2 font-medium">板块</th>
            <th className="pb-2 font-medium">涨幅</th>
            <th className="pb-2 font-medium">领涨股</th>
          </tr>
        </thead>
        <tbody>
          {sectors.map((s, i) => (
            <tr key={i} className="border-b border-slate-100">
              <td className="py-2 font-medium text-slate-800">{s["板块名称"]}</td>
              <td className={`py-2 ${s["涨跌幅"] >= 0 ? "text-red-500" : "text-green-500"}`}>
                {s["涨跌幅"] >= 0 ? "+" : ""}{s["涨跌幅"].toFixed(2)}%
              </td>
              <td className="py-2 text-slate-600">{s["领涨股票"]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function MarketDashboard() {
  const indicesQuery = useQuery({
    queryKey: ["market-indices"],
    queryFn: getMarketIndices,
    refetchInterval: 60_000,
  })
  const sectorsQuery = useQuery({
    queryKey: ["market-sectors"],
    queryFn: () => getHotSectors(5),
    refetchInterval: 60_000,
  })
  const sentimentQuery = useQuery({
    queryKey: ["market-sentiment"],
    queryFn: getMarketSentiment,
    refetchInterval: 60_000,
  })

  const loading = indicesQuery.isLoading || sectorsQuery.isLoading || sentimentQuery.isLoading
  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-200 border-t-indigo-600" />
      </div>
    )
  }

  const indices = indicesQuery.data?.indices || []
  const sectors = sectorsQuery.data?.sectors || []
  const sentiment = sentimentQuery.data
  const up = sentiment?.["上涨家数"] || 0
  const down = sentiment?.["下跌家数"] || 0
  const errors = [
    indicesQuery.data?.error,
    sectorsQuery.data?.error,
    sentimentQuery.data?.error,
  ].filter(Boolean)

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-bold text-slate-900">🌏 A股市场全览</h2>
      </div>

      {errors.length > 0 && (
        <div className="rounded-xl border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm text-yellow-700">
          部分行情数据获取失败: {errors.join("; ")}
        </div>
      )}

      {/* Index cards */}
      {indices.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-5">
          {indices.map((idx, i) => (
            <IndexCard key={i} index={idx} />
          ))}
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        {/* Sentiment */}
        <div className="af-card space-y-3">
          <h3 className="font-semibold text-slate-800">🌡️ 市场情绪</h3>
          <SentimentBar up={up} down={down} />
          <div className="flex justify-between text-sm">
            <span className="text-red-500">上涨 {up}</span>
            <span className="text-green-500">下跌 {down}</span>
          </div>
          {sentiment && (
            <div className="flex gap-4 text-sm text-slate-600">
              <span>涨停 {sentiment["涨停家数"]}</span>
              <span>跌停 {sentiment["跌停家数"]}</span>
              {sentiment["市场宽度"] && (
                <span>宽度 {(sentiment["市场宽度"] * 100).toFixed(1)}%</span>
              )}
              {sentiment["情绪描述"] && (
                <span className="text-indigo-600">{sentiment["情绪描述"]}</span>
              )}
            </div>
          )}
        </div>

        {/* Hot sectors */}
        <div className="af-card space-y-3">
          <h3 className="font-semibold text-slate-800">🔥 领涨行业板块</h3>
          <SectorTable sectors={sectors} />
        </div>
      </div>
    </div>
  )
}
