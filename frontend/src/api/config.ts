import client from "./client"
import type { AppConfig } from "../types"

export function getConfig(): Promise<AppConfig> {
  return client.get("/config/").then((r) => r.data)
}

export function updateConfig(payload: Partial<AppConfig>): Promise<AppConfig> {
  return client.put("/config/", payload).then((r) => r.data)
}

export function getSupportedModels(): Promise<{ supported_models: string[] }> {
  return client.get("/config/models").then((r) => r.data)
}
