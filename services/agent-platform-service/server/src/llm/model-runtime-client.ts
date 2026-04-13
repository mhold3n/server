/**
 * HTTP client for Python model-runtime: strict /infer and /solve routes.
 *
 * For agents: no model IDs here — server resolves from models.yaml.
 */

import type { PlatformConfig } from "../config.js"

export type ModelRuntimeInferResponse = {
  usage: { prompt_tokens: number; completion_tokens: number; latency_ms: number }
  model_id_resolved: string
  text?: string
  structured_output?: Record<string, unknown>
}

function base(cfg: PlatformConfig): string {
  const b = cfg.modelRuntimeBaseUrl
  if (!b) {
    throw new Error("modelRuntimeBaseUrl unset (MODEL_RUNTIME_URL)")
  }
  return b.replace(/\/$/, "")
}

export async function postInferGeneral(
  cfg: PlatformConfig,
  body: Record<string, unknown>,
  workflowRoot: boolean,
): Promise<ModelRuntimeInferResponse> {
  const url = `${base(cfg)}/infer/general?workflow_root=${workflowRoot ? "true" : "false"}`
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const t = await res.text()
    throw new Error(`infer/general ${res.status}: ${t}`)
  }
  return (await res.json()) as ModelRuntimeInferResponse
}

export async function postInferCoding(
  cfg: PlatformConfig,
  body: Record<string, unknown>,
): Promise<ModelRuntimeInferResponse> {
  const res = await fetch(`${base(cfg)}/infer/coding`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const t = await res.text()
    throw new Error(`infer/coding ${res.status}: ${t}`)
  }
  return (await res.json()) as ModelRuntimeInferResponse
}

export async function postInferMultimodal(
  cfg: PlatformConfig,
  body: Record<string, unknown>,
): Promise<ModelRuntimeInferResponse> {
  const res = await fetch(`${base(cfg)}/infer/multimodal`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const t = await res.text()
    throw new Error(`infer/multimodal ${res.status}: ${t}`)
  }
  return (await res.json()) as ModelRuntimeInferResponse
}
