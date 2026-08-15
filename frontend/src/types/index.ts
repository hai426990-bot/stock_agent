// Wire-contract types are derived from the backend OpenAPI schema
// (src/types/api.generated.ts, regenerated via scripts/gen_openapi.py +
// openapi-typescript — CI fails if they drift). Types that are richer than
// the wire schema (e.g. AnalysisDetail.final_state) stay hand-written here.
import type { components } from "./api.generated"

export type AnalysisCreateResponse = components["schemas"]["AnalysisCreateOut"]
export type AnalysisListItem = components["schemas"]["AnalysisListItem"]

export interface MarketIndex {
  name: string
  price: number
  change_pct: number
}

export interface HotSector {
  "板块名称": string
  "涨跌幅": number
  "领涨股票": string
}

export interface MarketSentiment {
  "上涨家数": number
  "下跌家数": number
  "涨停家数": number
  "跌停家数": number
  "市场宽度": number
  "情绪描述": string
}

export interface BacktestCandidate {
  label: string
  name: string
  params: Record<string, unknown>
  metrics: {
    sharpe: number
    cagr: number
    max_drawdown: number
    win_rate: number
    total_return?: number
    volatility?: number
    calmar?: number
    trade_count?: number
    turnover?: number
  }
  summary: string
}

export interface RiskAssessment {
  decision: string
  reason: string
  review_count?: number
  review_date?: string
}

export interface NodeEvent {
  event: "node" | "done" | "error"
  seq?: number
  node?: string
  status?: "completed" | "error"
  message?: string
  report_id?: string
}

export interface AnalysisDetail {
  id: string
  query: string
  stock_code: string
  stock_name: string
  is_sector: boolean
  sector_type: string
  status: string
  error: string
  final_state: {
    stock_code?: string
    stock_name?: string
    is_sector?: boolean
    news_analysis?: string
    sentiment_score?: number
    fear_greed_index?: number
    quant_data?: {
      backtest_candidates?: BacktestCandidate[]
      market_sentiment?: MarketSentiment
      valuation_history?: {
        latest_pe: number
        latest_pb: number
        pe_percentile: number
        pb_percentile: number
      }
    }
    technical_indicators?: Record<string, unknown>
    strategy_report?: string
    risk_assessment?: RiskAssessment | string
    telegraph_analysis?: {
      market_sentiment: string
      important_events: Array<{ title: string; impact: string; description: string }>
      opportunities: string[]
      summary: string
    }
    telegraph_news?: Array<{
      time: string
      title: string
      content: string
      stocks?: string[]
    }>
  }
  config_snapshot: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface AppConfig {
  api_base: string
  api_key: string
  has_api_key: boolean
  model_name: string
  supported_models: string[]
  llm: {
    temperature: number
    max_tokens: number
    thinking_mode: boolean
  }
  backtest: {
    days: number
    cash: number
  }
  web: {
    page_title: string
  }
}

export type AnalysisStatus = "pending" | "running" | "completed" | "failed"
