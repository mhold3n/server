import { defineTool } from "@server/open-multi-agent"
import { z } from "zod"
import type { PlatformConfig } from "../config.js"
import { getDomainData, searchKnowledgeBase } from "../tools/wrkhrs.js"

/** WrkHrs-backed tools for Open Multi-Agent (no shell / filesystem builtins). */
export function createWrkhrsOmaTools(cfg: PlatformConfig) {
  return [
    defineTool({
      name: "search_knowledge_base",
      description: "Search the RAG knowledge base with optional domain weighting.",
      inputSchema: z.object({
        query: z.string(),
        domain_weights: z.record(z.number()).optional(),
      }),
      execute: async ({ query, domain_weights }) => ({
        data: await searchKnowledgeBase(cfg, query, domain_weights ?? {}),
      }),
    }),
    defineTool({
      name: "get_domain_data",
      description: "Get domain-specific data from MCP HTTP services.",
      inputSchema: z.object({
        domain: z.string(),
        query: z.string(),
      }),
      execute: async ({ domain, query }) => ({
        data: await getDomainData(cfg, domain, query),
      }),
    }),
    defineTool({
      name: "martymedia_whisper_srt",
      description:
        "Generate SRT captions via MartyMedia whisper automation (tool-registry-backed).",
      inputSchema: z.object({
        input: z.string(),
        output_dir: z.string(),
        language: z.enum(["en", "es"]),
        model: z.string().optional(),
      }),
      execute: async ({ input, output_dir, language, model }) => {
        const res = await fetch(`${cfg.toolRegistryUrl}/tools/martymedia_whisper_srt/execute`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            tool_name: "martymedia_whisper_srt",
            parameters: { input, output_dir, language, model: model ?? "" },
          }),
          signal: AbortSignal.timeout(60_000),
        })
        if (!res.ok) {
          return { data: `tool-registry error: ${res.status}`, isError: true }
        }
        const payload = (await res.json()) as any
        return { data: payload, isError: payload?.success === false }
      },
    }),
    defineTool({
      name: "larrak_audio_ingest",
      description: "Run larrak-audio ingest via tool registry.",
      inputSchema: z.object({
        source: z.string(),
        type: z.string().optional(),
        marker_extra_args: z.array(z.string()).optional(),
      }),
      execute: async ({ source, type, marker_extra_args }) => {
        const res = await fetch(`${cfg.toolRegistryUrl}/tools/larrak_audio_ingest/execute`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            tool_name: "larrak_audio_ingest",
            parameters: {
              source,
              type: type ?? "",
              // Encode repeatable args for simple CLI plugin expansion.
              marker_extra_args: (marker_extra_args ?? []).join("||"),
            },
          }),
          signal: AbortSignal.timeout(60_000),
        })
        if (!res.ok) {
          return { data: `tool-registry error: ${res.status}`, isError: true }
        }
        const payload = (await res.json()) as any
        return { data: payload, isError: payload?.success === false }
      },
    }),
    defineTool({
      name: "larrak_audio_build",
      description: "Run larrak-audio build via tool registry.",
      inputSchema: z.object({
        source_id: z.string(),
        enhance: z.enum(["on", "off"]).optional(),
      }),
      execute: async ({ source_id, enhance }) => {
        const res = await fetch(`${cfg.toolRegistryUrl}/tools/larrak_audio_build/execute`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            tool_name: "larrak_audio_build",
            parameters: { source_id, enhance: enhance ?? "on" },
          }),
          signal: AbortSignal.timeout(60_000),
        })
        if (!res.ok) {
          return { data: `tool-registry error: ${res.status}`, isError: true }
        }
        const payload = (await res.json()) as any
        return { data: payload, isError: payload?.success === false }
      },
    }),
  ] as const
}
