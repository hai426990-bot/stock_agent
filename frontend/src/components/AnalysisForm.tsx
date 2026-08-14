import { useState, type FormEvent } from "react"

interface AnalysisFormProps {
  onSubmit: (query: string) => void
  disabled: boolean
  loading: boolean
}

export default function AnalysisForm({ onSubmit, disabled, loading }: AnalysisFormProps) {
  const [query, setQuery] = useState("")

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    const trimmed = query.trim()
    if (!trimmed) return
    onSubmit(trimmed)
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="输入股票代码（如 600519）或名称（如 贵州茅台）..."
        disabled={disabled}
        className="flex-1 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 outline-none transition-colors focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 disabled:opacity-50"
      />
      <button
        type="submit"
        disabled={disabled || !query.trim()}
        className="flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-indigo-700 disabled:opacity-50"
      >
        {loading ? (
          <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
        ) : (
          "分析"
        )}
      </button>
    </form>
  )
}
