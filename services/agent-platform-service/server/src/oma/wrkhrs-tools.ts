import { defineTool } from "@server/open-multi-agent"
import { z } from "zod"
import type { PlatformConfig } from "../config.js"
import {
  actOnContainerGui,
  closeContainerGui,
  launchContainerGui,
  listContainerGuiArtifacts,
  recordContainerGui,
  resolveContainerGui,
  screenshotContainerGui,
} from "../tools/container-gui.js"
import { getDomainData, searchKnowledgeBase } from "../tools/wrkhrs.js"

/** WrkHrs-backed tools for Open Multi-Agent (no shell / filesystem builtins). */
export function createWrkhrsOmaTools(cfg: PlatformConfig) {
  const isToolRegistryFailure = (payload: unknown): boolean => {
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) return false
    return (payload as Record<string, unknown>).success === false
  }

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
      name: "container_gui.launch",
      description:
        "Resolve and launch a knowledge-pool container GUI session through noVNC for OpenClaw browser control.",
      inputSchema: z.object({
        target_ref: z.string(),
        allow_unverified: z.boolean().optional(),
        novnc_port: z.number().int().positive().optional(),
        artifact_output_dir: z.string().optional(),
      }),
      execute: async (input) => launchContainerGui(cfg, input),
    }),
    defineTool({
      name: "container_gui.resolve",
      description: "Resolve the default knowledge-pool container GUI session for a module or environment ref.",
      inputSchema: z.object({
        target_ref: z.string(),
        allow_unverified: z.boolean().optional(),
      }),
      execute: async (input) => resolveContainerGui(cfg, input),
    }),
    defineTool({
      name: "container_gui.screenshot",
      description:
        "Open an optional noVNC URL in OpenClaw browser control and capture a screenshot artifact.",
      inputSchema: z.object({
        url: z.string().optional(),
        output: z.string().optional(),
        target_id: z.string().optional(),
        trace_path: z.string().optional(),
        dry_run: z.boolean().optional(),
      }),
      execute: async (input) => screenshotContainerGui(cfg, input),
    }),
    defineTool({
      name: "container_gui.act",
      description:
        "Perform an OpenClaw browser action against the active noVNC-controlled container GUI.",
      inputSchema: z.object({
        action: z.enum(["open", "screenshot", "snapshot", "click", "type", "press", "wait"]),
        payload: z.record(z.unknown()).optional(),
        trace_path: z.string().optional(),
        dry_run: z.boolean().optional(),
      }),
      execute: async (input) => actOnContainerGui(cfg, input),
    }),
    defineTool({
      name: "container_gui.record",
      description: "Capture screenshot and DOM/accessibility snapshot evidence for a container GUI session.",
      inputSchema: z.object({
        url: z.string().optional(),
        screenshot_output: z.string().optional(),
        snapshot_output: z.string().optional(),
        trace_path: z.string().optional(),
        dry_run: z.boolean().optional(),
      }),
      execute: async (input) => recordContainerGui(cfg, input),
    }),
    defineTool({
      name: "container_gui.artifacts",
      description: "List generated artifact files for a knowledge-pool GUI session.",
      inputSchema: z.object({
        gui_session_ref: z.string(),
      }),
      execute: async (input) => listContainerGuiArtifacts(cfg, input),
    }),
    defineTool({
      name: "container_gui.close",
      description: "Close a launched knowledge-pool container GUI session.",
      inputSchema: z.object({
        container: z.string(),
      }),
      execute: async (input) => closeContainerGui(cfg, input),
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
        const payload: unknown = await res.json()
        return { data: JSON.stringify(payload), isError: isToolRegistryFailure(payload) }
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
        const payload: unknown = await res.json()
        return { data: JSON.stringify(payload), isError: isToolRegistryFailure(payload) }
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
        const payload: unknown = await res.json()
        return { data: JSON.stringify(payload), isError: isToolRegistryFailure(payload) }
      },
    }),
  ] as const
}
