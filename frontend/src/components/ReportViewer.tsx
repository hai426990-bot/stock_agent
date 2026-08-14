interface ReportViewerProps {
  content: string
  stockName?: string
  stockCode?: string
}

export default function ReportViewer({ content, stockName, stockCode }: ReportViewerProps) {
  if (!content || content === "未生成") {
    return (
      <div className="af-card py-10 text-center text-sm text-slate-400">
        报告正文未生成或为空
      </div>
    )
  }

  const htmlContent = content
    .replace(/^### (.+)$/gm, '<h3 class="text-lg font-bold text-slate-900 mt-6 mb-2">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="text-xl font-bold text-slate-900 mt-8 mb-3 border-l-4 border-indigo-400 pl-3">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 class="text-2xl font-extrabold text-slate-900 mt-8 mb-4">$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-slate-900 bg-gradient-to-r from-indigo-100 to-transparent px-1 rounded">$1</strong>')
    .replace(/\n\n/g, '</p><p class="mb-4 leading-relaxed text-slate-700">')
    .replace(/^- (.+)$/gm, '</p><li class="ml-4 list-disc text-slate-700">$1</li>')
    .replace(/^(\d+)\. (.+)$/gm, '</p><li class="ml-4 list-decimal text-slate-700">$1. $2</li>')

  return (
    <div className="af-card">
      <div className="mb-4 border-b border-slate-200 pb-3">
        <h2 className="text-lg font-bold text-slate-900">
          AlphaFlow 报告 · {stockName} ({stockCode})
        </h2>
      </div>
      <div
        className="prose prose-slate max-w-none"
        dangerouslySetInnerHTML={{ __html: `<p>${htmlContent}</p>` }}
      />
    </div>
  )
}
