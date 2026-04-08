/**
 * HTTP client for Python model-runtime: strict /infer and /solve routes.
 *
 * For agents: no model IDs here — server resolves from models.yaml.
 */

import type { PlatformConfig } from "../config.js"

export type OrchestrationPacket = Record<string, unknown>
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
  body: OrchestrationPacket,
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

export async function postSolveMechanics(
  cfg: PlatformConfig,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const res = await fetch(`${base(cfg)}/solve/mechanics`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const t = await res.text()
    throw new Error(`solve/mechanics ${res.status}: ${t}`)
  }
  return (await res.json()) as Record<string, unknown>
}

export async function postSolveVerify(
  cfg: PlatformConfig,
  report: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const res = await fetch(`${base(cfg)}/solve/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(report),
  })
  if (!res.ok) {
    const t = await res.text()
    throw new Error(`solve/verify ${res.status}: ${t}`)
  }
  return (await res.json()) as Record<string, unknown>
}
