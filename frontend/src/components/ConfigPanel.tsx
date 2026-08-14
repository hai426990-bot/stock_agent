import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { getConfig, updateConfig } from "../api/config"

export default function ConfigPanel() {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [message, setMessage] = useState("")

  const configQuery = useQuery({
    queryKey: ["config"],
    queryFn: getConfig,
  })

  // GET /api/config/ already returns supported_models — no separate request needed
  const models = configQuery.data?.supported_models || []

  const updateMutation = useMutation({
    mutationFn: updateConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["config"] })
      setMessage("✅ 配置已保存")
      setEditing(false)
      setTimeout(() => setMessage(""), 3000)
    },
    onError: () => {
      setMessage("❌ 保存失败")
    },
  })

  const [form, setForm] = useState({
    model_name: "",
    api_base: "",
    api_key: "",
    temperature: 0.3,
    max_tokens: 8192,
    thinking_mode: true,
    backtest_days: 365,
    backtest_cash: 100000,
  })

  const startEdit = () => {
    const cfg = configQuery.data
    if (!cfg) return
    setForm({
      model_name: cfg.model_name || "",
      api_base: cfg.api_base || "",
      api_key: "",
      temperature: cfg.llm?.temperature ?? 0.3,
      max_tokens: cfg.llm?.max_tokens ?? 8192,
      thinking_mode: cfg.llm?.thinking_mode ?? true,
      backtest_days: cfg.backtest?.days ?? 365,
      backtest_cash: cfg.backtest?.cash ?? 100000,
    })
    setEditing(true)
    setMessage("")
  }

  const handleSave = () => {
    updateMutation.mutate({
      model_name: form.model_name,
      api_base: form.api_base,
      api_key: form.api_key || undefined,
      llm: {
        temperature: form.temperature,
        max_tokens: form.max_tokens,
        thinking_mode: form.thinking_mode,
      },
      backtest: {
        days: form.backtest_days,
        cash: form.backtest_cash,
      },
    })
  }

  const config = configQuery.data
  const isLoading = configQuery.isLoading

  if (isLoading) {
    return <div className="px-4 py-8 text-center text-sm text-slate-400">加载中...</div>
  }

  if (!editing) {
    return (
      <div className="af-card space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-bold text-slate-900">⚙️ 系统配置</h3>
          <button onClick={startEdit} className="rounded-lg bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100">
            编辑
          </button>
        </div>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between"><span className="text-slate-500">模型</span><span>{config?.model_name || "-"}</span></div>
          <div className="flex justify-between"><span className="text-slate-500">API Base</span><span className="truncate pl-4">{config?.api_base || "-"}</span></div>
          <div className="flex justify-between"><span className="text-slate-500">API Key</span><span>{config?.has_api_key ? "✅ 已配置" : "❌ 未配置"}</span></div>
          <div className="flex justify-between"><span className="text-slate-500">Temperature</span><span>{config?.llm?.temperature ?? "-"}</span></div>
          <div className="flex justify-between"><span className="text-slate-500">回测天数</span><span>{config?.backtest?.days ?? "-"}天</span></div>
          <div className="flex justify-between"><span className="text-slate-500">初始资金</span><span>¥{config?.backtest?.cash?.toLocaleString() ?? "-"}</span></div>
        </div>
        {message && <div className="text-sm text-green-600">{message}</div>}
      </div>
    )
  }

  return (
    <div className="af-card space-y-4">
      <h3 className="font-bold text-slate-900">编辑配置</h3>

      <div className="space-y-3">
        <div>
          <label className="block text-xs font-medium text-slate-500">模型</label>
          <select
            value={form.model_name}
            onChange={(e) => setForm(f => ({ ...f, model_name: e.target.value }))}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-400"
          >
            {models.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-500">API Base URL</label>
          <input
            type="text" value={form.api_base}
            onChange={(e) => setForm(f => ({ ...f, api_base: e.target.value }))}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-400"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-500">API Key (留空不修改)</label>
          <input
            type="password" value={form.api_key}
            onChange={(e) => setForm(f => ({ ...f, api_key: e.target.value }))}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-400"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-slate-500">Temperature</label>
            <input
              type="number" min={0} max={1} step={0.1} value={form.temperature}
              onChange={(e) => setForm(f => ({ ...f, temperature: +e.target.value }))}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-400"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500">Max Tokens</label>
            <select
              value={form.max_tokens}
              onChange={(e) => setForm(f => ({ ...f, max_tokens: +e.target.value }))}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-400"
            >
              {[1024, 2048, 4096, 8192, 16384].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <input
            type="checkbox" id="thinking" checked={form.thinking_mode}
            onChange={(e) => setForm(f => ({ ...f, thinking_mode: e.target.checked }))}
            className="rounded border-slate-300"
          />
          <label htmlFor="thinking" className="text-sm text-slate-700">深度思考模式</label>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-slate-500">回测天数</label>
            <input
              type="number" min={30} max={3650} value={form.backtest_days}
              onChange={(e) => setForm(f => ({ ...f, backtest_days: +e.target.value }))}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-400"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500">初始资金</label>
            <input
              type="number" min={1000} value={form.backtest_cash}
              onChange={(e) => setForm(f => ({ ...f, backtest_cash: +e.target.value }))}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-400"
            />
          </div>
        </div>
      </div>

      <div className="flex gap-2">
        <button onClick={handleSave} disabled={updateMutation.isPending}
          className="flex-1 rounded-lg bg-indigo-600 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50">
          {updateMutation.isPending ? "保存中..." : "💾 保存配置"}
        </button>
        <button onClick={() => setEditing(false)}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50">
          取消
        </button>
      </div>
      {message && <div className="text-sm text-green-600">{message}</div>}
    </div>
  )
}
