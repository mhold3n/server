import type { PlatformConfig } from "../config.js"

export type ChatMessage = { role: string; content: string }

export async function searchKnowledgeBase(
  cfg: PlatformConfig,
  query: string,
  domainWeights: Record<string, number> = {},
): Promise<string> {
  try {
    const res = await fetch(`${cfg.ragUrl}/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, domain_weights: domainWeights, k: 5 }),
      signal: AbortSignal.timeout(15_000),
    })
    if (!res.ok) {
      return `Error searching knowledge base: ${res.status}`
    }
    const data = (await res.json()) as { evidence?: string }
    return data.evidence ?? "No evidence found"
  } catch (e) {
    return `Error searching knowledge base: ${e instanceof Error ? e.message : String(e)}`
  }
}

export async function transcribeAudio(
  cfg: PlatformConfig,
  audioData: string,
): Promise<string> {
  try {
    const res = await fetch(`${cfg.asrUrl}/transcribe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ audio_data: audioData }),
      signal: AbortSignal.timeout(30_000),
    })
    if (!res.ok) {
      return `Error transcribing audio: ${res.status}`
    }
    const data = (await res.json()) as { transcript?: string }
    return data.transcript ?? "No transcript generated"
  } catch (e) {
    return `Error transcribing audio: ${e instanceof Error ? e.message : String(e)}`
  }
}

export async function getDomainData(
  cfg: PlatformConfig,
  domain: string,
  query: string,
): Promise<string> {
  try {
    const res = await fetch(`${cfg.mcpUrl}/${domain}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
      signal: AbortSignal.timeout(15_000),
    })
    if (!res.ok) {
      return `Error getting domain data: ${res.status}`
    }
    const data = (await res.json()) as { data?: string }
    return data.data ?? "No domain data found"
  } catch (e) {
    return `Error getting domain data: ${e instanceof Error ? e.message : String(e)}`
  }
}

export async function getAvailableTools(
  cfg: PlatformConfig,
): Promise<Array<Record<string, unknown>>> {
  try {
    const res = await fetch(`${cfg.toolRegistryUrl}/tools`, {
      signal: AbortSignal.timeout(10_000),
    })
    if (!res.ok) {
      return []
    }
    const data = (await res.json()) as { tools?: Array<Record<string, unknown>> }
    return data.tools ?? []
  } catch {
    return []
  }
}

export function extractDomainWeightsFromMessages(
  messages: ChatMessage[],
): Record<string, number> {
  const domainWeights: Record<string, number> = {}
  for (const msg of messages) {
    if (msg.role !== "system") continue
    const content = msg.content
    if (!content.includes("Domain Analysis:")) continue
    try {
      for (const part of content.split(/[\n,]/)) {
        const m = part.match(/Chemistry\s*=\s*([\d.]+)/i)
        if (m) domainWeights.chemistry = parseFloat(m[1]!)
        const m2 = part.match(/Mechanical\s*=\s*([\d.]+)/i)
        if (m2) domainWeights.mechanical = parseFloat(m2[1]!)
        const m3 = part.match(/Materials\s*=\s*([\d.]+)/i)
        if (m3) domainWeights.materials = parseFloat(m3[1]!)
      }
    } catch {
      /* ignore parse errors */
    }
  }
  return domainWeights
}
