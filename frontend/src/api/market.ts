import client from "./client"
import type { MarketIndex, HotSector, MarketSentiment } from "../types"

export function getMarketIndices(): Promise<{ indices: MarketIndex[]; error?: string }> {
  return client.get("/market/indices").then((r) => r.data)
}

export function getHotSectors(limit = 5): Promise<{ sectors: HotSector[]; error?: string }> {
  return client.get("/market/hot-sectors", { params: { limit } }).then((r) => r.data)
}

export function getMarketSentiment(): Promise<MarketSentiment & { error?: string }> {
  return client.get("/market/sentiment").then((r) => r.data)
}
