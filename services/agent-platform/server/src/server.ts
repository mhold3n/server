import crypto from "node:crypto"
import { pathToFileURL } from "node:url"
import Fastify from "fastify"
import { z } from "zod"
import {
  Agent,
  OpenMultiAgent,
  ToolExecutor,
  ToolRegistry,
  type AgentConfig,
  type TeamConfig,
} from "@server/open-multi-agent"
import { loadConfig } from "./config.js"
import { LLMManager } from "./llm/manager.js"
import { createWrkhrsOmaTools } from "./oma/wrkhrs-tools.js"
import type { ChatMessage } from "./tools/wrkhrs.js"
import { createChatWorkflow } from "./workflow/graph.js"
import {
  completeWorkflowRun,
  createWorkflowRun,
  failWorkflowRun,
  cancelWorkflowRun,
  getWorkflowRun,
} from "./workflow/run-store.js"

const WORKFLOW_NAMES = [
  "wrkhrs_chat",
  "rag_retrieval",
  "tool_execution",
  "github_integration",
  "policy_validation",
] as const

export function buildServer() {
  const cfg = loadConfig()
  const llm = new LLMManager(cfg)
  const chatWorkflow = createChatWorkflow(cfg, llm)
  const omaTools = createWrkhrsOmaTools(cfg)

  const defaultModel = process.env.OMA_DEFAULT_MODEL ?? "claude-sonnet-4-20250514"
  const defaultProvider =
    (process.env.OMA_DEFAULT_PROVIDER as "anthropic" | "openai" | undefined) ??
    "anthropic"

  function createOma(): OpenMultiAgent {
    return new OpenMultiAgent({
      defaultModel,
      defaultProvider,
      enableBuiltInTools: false,
      extraTools: [...omaTools],
    })
  }

  const app = Fastify({ logger: true })

  app.get("/health", async () => {
    const llmHealth = await llm.healthCheck()
    return {
      status: "healthy",
      timestamp: new Date().toISOString(),
      workflow_ready: true,
      llm_backend: {
        healthy: llmHealth.healthy,
        backend: llmHealth.backend,
        detail: llmHealth.detail,
      },
      orchestrator: "typescript-agent-platform",
    }
  })

  const chatBody = z.object({
    messages: z.array(z.object({ role: z.string(), content: z.string() })),
    model: z.string().optional(),
    temperature: z.number().optional(),
    max_tokens: z.number().optional(),
  })

  app.post("/chat", async (request, reply) => {
    const parsed = chatBody.safeParse(request.body)
    if (!parsed.success) {
      return reply.status(400).send({ detail: parsed.error.flatten() })
    }
    const body = parsed.data
    const result = await chatWorkflow.invoke({
      messages: body.messages as ChatMessage[],
      current_step: "analyze",
      tools_needed: [],
      tool_results: {},
    })

    const now = Math.floor(Date.now() / 1000)
    return {
      id: `chatcmpl-${now}`,
      object: "chat.completion",
      created: now,
      model: body.model ?? "orchestrator",
      choices: [
        {
          index: 0,
          message: {
            role: "assistant",
            content: result.final_response ?? "No response generated",
          },
          finish_reason: "stop",
        },
      ],
      usage: {
        prompt_tokens: 0,
        completion_tokens: 0,
        total_tokens: 0,
      },
    }
  })

  app.get("/workflow/status", async () => {
    try {
      const toolsMod = await import("./tools/wrkhrs.js")
      const tools = await toolsMod.getAvailableTools(cfg)
      return {
        status: "active",
        available_tools: tools.length,
        workflow_nodes: ["analyze", "gather_context", "generate_response"],
        orchestrator: "langgraph-typescript",
      }
    } catch (e) {
      return { status: "error", message: String(e) }
    }
  })

  app.get("/llm/info", async () => {
    return {
      backend_info: llm.getBackendInfo(),
      health: await llm.healthCheck(),
      available_models: await llm.listModels(),
    }
  })

  app.post<{ Params: { backend_type: string } }>(
    "/llm/switch/:backend_type",
    async (request, reply) => {
      const backend_type = request.params.backend_type.toLowerCase()
      if (!["ollama", "vllm", "mock", "none", "disabled"].includes(backend_type)) {
        return reply.status(400).send({
          detail: "Backend must be ollama, vllm, mock, none, or disabled",
        })
      }
      return {
        success: false,
        message:
          "Backend is controlled via LLM_BACKEND env in the TS orchestrator; restart service to switch.",
        requested: backend_type,
      }
    },
  )

  app.get("/v1/workflows", async () => ({
    workflows: [...WORKFLOW_NAMES],
  }))

  app.get<{ Params: { name: string } }>(
    "/v1/workflows/:name/schema",
    async (request) => {
      const name = request.params.name
      return {
        name,
        input: { type: "object" },
        output: { type: "object" },
      }
    },
  )

  app.post("/v1/workflows/execute", async (request, reply) => {
    const body = request.body as {
      workflow_name?: string
      input_data?: Record<string, unknown>
      workflow_config?: Record<string, unknown>
    }
    const workflowName = body.workflow_name ?? "wrkhrs_chat"
    const inputData = body.input_data ?? {}
    const id = crypto.randomUUID()
    const started = Date.now()
    createWorkflowRun(id, workflowName)

    try {
      let output: unknown

      if (workflowName === "wrkhrs_chat" || workflowName === "default") {
        const messages = (inputData.messages as ChatMessage[]) ?? [
          { role: "user", content: String(inputData.prompt ?? inputData.query ?? "") },
        ]
        const result = await chatWorkflow.invoke({
          messages,
          current_step: "analyze",
          tools_needed: [],
          tool_results: {},
        })
        output = { final_response: result.final_response, tool_results: result.tool_results }
      } else if (workflowName === "rag_retrieval") {
        const { searchKnowledgeBase } = await import("./tools/wrkhrs.js")
        const evidence = await searchKnowledgeBase(
          cfg,
          String(inputData.query ?? ""),
          (inputData.domain_weights as Record<string, number>) ?? {},
        )
        output = { evidence, top_k: inputData.top_k, min_score: inputData.min_score }
      } else {
        output = {
          note: "stub",
          workflow_name: workflowName,
          input_data: inputData,
          workflow_config: body.workflow_config,
        }
      }

      const duration = (Date.now() - started) / 1000
      completeWorkflowRun(id, output)
      const rec = getWorkflowRun(id)
      return {
        status: rec?.status ?? "completed",
        workflow_id: id,
        workflow_name: workflowName,
        duration,
        result: output,
      }
    } catch (e) {
      failWorkflowRun(id, e instanceof Error ? e.message : String(e))
      return reply.status(500).send({
        status: "failed",
        workflow_id: id,
        error: e instanceof Error ? e.message : String(e),
      })
    }
  })

  app.get<{ Params: { id: string } }>(
    "/v1/workflows/:id/status",
    async (request, reply) => {
      const rec = getWorkflowRun(request.params.id)
      if (!rec) {
        return reply.status(404).send({ detail: "workflow not found" })
      }
      return {
        id: rec.id,
        status: rec.status,
        workflow_name: rec.workflow_name,
        result: rec.result,
      }
    },
  )

  app.post<{ Params: { id: string } }>(
    "/v1/workflows/:id/cancel",
    async (request) => {
      const ok = cancelWorkflowRun(request.params.id)
      return {
        id: request.params.id,
        status: ok ? "cancelled" : "completed",
      }
    },
  )

  const agentRunBody = z.object({
    agent: z.object({
      name: z.string(),
      model: z.string(),
      provider: z.enum(["anthropic", "openai"]).optional(),
      systemPrompt: z.string().optional(),
      tools: z.array(z.string()).optional(),
      maxTurns: z.number().optional(),
    }),
    prompt: z.string(),
  })

  app.post("/v1/agents/run", async (request, reply) => {
    const parsed = agentRunBody.safeParse(request.body)
    if (!parsed.success) {
      return reply.status(400).send({ detail: parsed.error.flatten() })
    }
    const { agent: agentSpec, prompt } = parsed.data
    const registry = new ToolRegistry()
    for (const t of omaTools) {
      registry.register(t)
    }
    const executor = new ToolExecutor(registry)
    const agentConfig: AgentConfig = {
      name: agentSpec.name,
      model: agentSpec.model,
      provider: agentSpec.provider ?? defaultProvider,
      systemPrompt: agentSpec.systemPrompt,
      tools: agentSpec.tools ?? ["search_knowledge_base", "get_domain_data"],
      maxTurns: agentSpec.maxTurns ?? 8,
    }
    const agent = new Agent(agentConfig, registry, executor)
    const result = await agent.run(prompt)
    return {
      success: result.success,
      output: result.output,
      tokenUsage: result.tokenUsage,
      toolCalls: result.toolCalls,
    }
  })

  const teamSchema = z.object({
    name: z.string(),
    sharedMemory: z.boolean().optional(),
    maxConcurrency: z.number().optional(),
    agents: z.array(
      z.object({
        name: z.string(),
        model: z.string(),
        provider: z.enum(["anthropic", "openai"]).optional(),
        systemPrompt: z.string().optional(),
        tools: z.array(z.string()).optional(),
        maxTurns: z.number().optional(),
      }),
    ),
  })

  const teamRunBody = z.object({
    team: teamSchema,
    goal: z.string(),
  })

  app.post("/v1/teams/run", async (request, reply) => {
    const parsed = teamRunBody.safeParse(request.body)
    if (!parsed.success) {
      return reply.status(400).send({ detail: parsed.error.flatten() })
    }
    const body = parsed.data
    const teamConfig: TeamConfig = {
      name: body.team.name,
      sharedMemory: body.team.sharedMemory ?? true,
      maxConcurrency: body.team.maxConcurrency,
      agents: body.team.agents.map((a) => ({
        name: a.name,
        model: a.model,
        provider: a.provider ?? defaultProvider,
        systemPrompt: a.systemPrompt,
        tools: a.tools ?? ["search_knowledge_base", "get_domain_data"],
        maxTurns: a.maxTurns ?? 6,
      })),
    }
    try {
      const oma = createOma()
      const team = oma.createTeam(`${body.team.name}-${crypto.randomUUID()}`, teamConfig)
      const result = await oma.runTeam(team, body.goal)
      return {
        success: result.success,
        totalTokenUsage: result.totalTokenUsage,
        agentResults: Object.fromEntries(result.agentResults),
      }
    } catch (e) {
      request.log.error(e)
      return reply.status(500).send({
        error: e instanceof Error ? e.message : String(e),
      })
    }
  })

  const tasksRunBody = z.object({
    team: teamSchema,
    tasks: z.array(
      z.object({
        title: z.string(),
        description: z.string(),
        assignee: z.string().optional(),
        dependsOn: z.array(z.string()).optional(),
      }),
    ),
  })

  app.post("/v1/tasks/run", async (request, reply) => {
    const parsed = tasksRunBody.safeParse(request.body)
    if (!parsed.success) {
      return reply.status(400).send({ detail: parsed.error.flatten() })
    }
    const body = parsed.data
    const teamConfig: TeamConfig = {
      name: body.team.name,
      sharedMemory: body.team.sharedMemory ?? true,
      maxConcurrency: body.team.maxConcurrency,
      agents: body.team.agents.map((a) => ({
        name: a.name,
        model: a.model,
        provider: a.provider ?? defaultProvider,
        systemPrompt: a.systemPrompt,
        tools: a.tools ?? ["search_knowledge_base", "get_domain_data"],
        maxTurns: a.maxTurns ?? 6,
      })),
    }
    try {
      const oma = createOma()
      const team = oma.createTeam(`${body.team.name}-tasks-${crypto.randomUUID()}`, teamConfig)
      const result = await oma.runTasks(team, body.tasks)
      return {
        success: result.success,
        totalTokenUsage: result.totalTokenUsage,
        agentResults: Object.fromEntries(result.agentResults),
      }
    } catch (e) {
      request.log.error(e)
      return reply.status(500).send({
        error: e instanceof Error ? e.message : String(e),
      })
    }
  })

  return app
}

async function main() {
  const app = buildServer()
  const port = Number(process.env.AGENT_PLATFORM_PORT ?? process.env.PORT ?? 8000)
  const host = process.env.AGENT_PLATFORM_HOST ?? "0.0.0.0"
  await app.listen({ port, host })
}

if (pathToFileURL(process.argv[1] ?? "").href === import.meta.url) {
  main().catch((err) => {
    console.error(err)
    process.exit(1)
  })
}
