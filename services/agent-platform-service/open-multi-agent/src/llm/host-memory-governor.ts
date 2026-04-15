/**
 * Host memory governor client (macOS unified memory).
 *
 * This module exists so the Ollama adapter can be safely used inside Docker
 * on macOS without crashing the host when memory is tight.
 *
 * It is intentionally conservative:
 * - It never kills processes.
 * - It only gates/defers Ollama calls until the host reports safe headroom.
 *
 * Security: requests require a bearer token when configured.
 */

export type GovernorProfile = 'blocked' | 'tiny' | 'small' | 'medium' | 'large' | 'default'

export interface GovernorRecommendation {
  allow_start: boolean
  target_profile: GovernorProfile
  reason?: string
}

export interface GovernorResponse {
  recommendation?: GovernorRecommendation
}

function env(key: string): string | undefined {
  const value = process.env[key]
  return value && value.trim().length > 0 ? value.trim() : undefined
}

export function governorUrl(): string | undefined {
  return env('HOST_MEMORY_GOVERNOR_URL') ?? env('MEMORY_GOVERNOR_URL')
}

export function governorToken(): string | undefined {
  return env('HOST_MEMORY_GOVERNOR_TOKEN') ?? env('MEMORY_GOVERNOR_TOKEN')
}

export async function fetchGovernorRecommendation(
  workload: string,
  abortSignal?: AbortSignal,
): Promise<GovernorRecommendation | undefined> {
  const base = governorUrl()
  if (!base) return undefined

  const url = `${base.replace(/\/$/, '')}/v1/recommendation?workload=${encodeURIComponent(workload)}`
  const token = governorToken()
  const res = await fetch(url, {
    method: 'GET',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    signal: abortSignal,
  })
  if (!res.ok) return undefined
  const data = (await res.json()) as GovernorResponse
  const rec = data.recommendation
  if (!rec) return undefined
  if (typeof rec.allow_start !== 'boolean') return undefined
  if (!rec.target_profile || typeof rec.target_profile !== 'string') return undefined
  return rec
}

export async function waitForGovernorAllowance(input: {
  workload: string
  abortSignal?: AbortSignal
  pollIntervalMs?: number
}): Promise<GovernorRecommendation | undefined> {
  const pollMs = input.pollIntervalMs ?? 1500
  for (;;) {
    const rec = await fetchGovernorRecommendation(input.workload, input.abortSignal).catch(() => undefined)
    if (!rec) return undefined
    if (rec.allow_start) return rec

    if (input.abortSignal?.aborted) {
      return rec
    }

    await new Promise<void>((resolve) => setTimeout(resolve, pollMs))
  }
}

