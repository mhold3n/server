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
  ] as const
}
