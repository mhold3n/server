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
import { executeBackendRun } from "./devplane/runner.js"
import {
  createBackendRun,
  getBackendRun,
  markRunCancelled,
} from "./devplane/run-store.js"
import { devPlaneRunCreateSchema } from "./devplane/types.js"
import { LLMManager } from "./llm/manager.js"
import { createWrkhrsOmaTools } from "./oma/wrkhrs-tools.js"
import type { ChatMessage } from "./tools/wrkhrs.js"
import { createChatWorkflow } from "./workflow/graph.js"
import { createEngineeringWorkflow } from "./workflow/engineering-graph.js"
import { createPhysicsHarnessWorkflow } from "./workflow/physics-harness-graph.js"
import {
  completeWorkflowRun,
  createWorkflowRun,
  failWorkflowRun,
  cancelWorkflowRun,
  getWorkflowRun,
} from "./workflow/run-store.js"

const WORKFLOW_NAMES = [
  "wrkhrs_chat",
  "engineering_workflow",
  "engineering_physics_v1",
  "rag_retrieval",
  "tool_execution",
  "github_integration",
  "policy_validation",
  "devplane_code_task",
] as const

export function buildServer() {
  const cfg = loadConfig()
  const llm = new LLMManager(cfg)
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

  async function callApiBrain(packet: string): Promise<string> {
    if (!cfg.apiBrainEnabled) {
      return "API brain disabled."
    }
    const model = cfg.apiBrainModel || defaultModel
    const provider = cfg.apiBrainProvider || defaultProvider
    const registry = new ToolRegistry()
    for (const t of omaTools) {
      registry.register(t)
    }
    const executor = new ToolExecutor(registry)
    const agentConfig: AgentConfig = {
      name: "api_brain",
      model,
      provider,
      systemPrompt:
        "You are the hosted API brain. Return a compact PLAN/REVIEW/DECISION/PATCH_GUIDANCE. " +
        "Do not ask questions. Do not include raw logs. Use only the provided packet.",
      tools: [],
      maxTurns: 4,
    }
    const agent = new Agent(agentConfig, registry, executor)
    const result = await agent.run(packet)
    return result.output ?? ""
  }

  const chatWorkflow = createChatWorkflow(cfg, llm, callApiBrain)
  const engineeringWorkflow = createEngineeringWorkflow(cfg, llm, callApiBrain)
  const physicsHarnessWorkflow = createPhysicsHarnessWorkflow(cfg)

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
        const workflowConfig = (body.workflow_config as Record<string, unknown> | undefined) ?? undefined
        const requiredToolResults = (inputData.required_tool_results as unknown[] | undefined) ?? undefined
        const result = await chatWorkflow.invoke({
          messages,
          current_step: "analyze",
          tools_needed: [],
          tool_results: {},
          workflow_config: workflowConfig,
          required_tool_results: requiredToolResults,
        })
        output = {
          final_response: result.final_response,
          tool_results: result.tool_results,
          api_brain: {
            escalation_count: (result as any).escalation_count ?? 0,
            packet: (result as any).api_brain_packet,
            output: (result as any).api_brain_output,
          },
        }
      } else if (workflowName === "engineering_workflow") {
        const tp = inputData.task_packet
        const messages = (inputData.messages as ChatMessage[]) ?? [
          {
            role: "user",
            content: String(
              (tp as Record<string, unknown> | undefined)?.objective ??
                inputData.prompt ??
                inputData.query ??
                "",
            ),
          },
        ]
        const workflowConfig =
          (body.workflow_config as Record<string, unknown> | undefined) ?? undefined
        const requiredToolResults =
          (inputData.required_tool_results as unknown[] | undefined) ?? undefined
        const result = await engineeringWorkflow.invoke({
          messages,
          current_step: "intake",
          tools_needed: [],
          tool_results: {},
          workflow_config: workflowConfig,
          request_context: (inputData.context as Record<string, unknown> | undefined) ?? undefined,
          required_tool_results: requiredToolResults,
          run_id: inputData.run_id as string | undefined,
          task_id: inputData.task_id as string | undefined,
          dossier_id: inputData.dossier_id as string | undefined,
          task_plan: (inputData.task_plan as Record<string, unknown> | undefined) ?? undefined,
          project_context:
            (inputData.project_context as Record<string, unknown> | undefined) ?? undefined,
          engineering_session_id:
            (inputData.engineering_session_id as string | undefined) ?? undefined,
          task_packet: tp as Record<string, unknown> | undefined,
          task_queue: (inputData.task_queue as Record<string, unknown> | undefined) ?? undefined,
          task_packets: (inputData.task_packets as Record<string, unknown>[] | undefined) ?? [],
          problem_brief:
            (inputData.problem_brief as Record<string, unknown> | undefined) ?? undefined,
          problem_brief_ref:
            (inputData.problem_brief_ref as string | undefined) ?? undefined,
          engineering_state:
            (inputData.engineering_state as Record<string, unknown> | undefined) ?? undefined,
          engineering_state_ref:
            (inputData.engineering_state_ref as string | undefined) ?? undefined,
          cost_ledger_entries: [],
        } as any)
        output = {
          final_response: result.final_response,
          tool_results: result.tool_results,
          referential_state: {
            run_id: result.run_id,
            task_id: result.task_id,
            dossier_id: result.dossier_id,
            engineering_session_id: result.engineering_session_id,
            problem_brief_ref: result.problem_brief_ref,
            engineering_state_ref: result.engineering_state_ref,
            active_task_packet_id: result.active_task_packet_id,
            dossier_snapshot: (result as { dossier_snapshot?: unknown })
              .dossier_snapshot,
          },
          problem_brief: (result as { problem_brief?: unknown }).problem_brief,
          engineering_state: (result as { engineering_state?: unknown }).engineering_state,
          task_queue: (result as { task_queue?: unknown }).task_queue,
          task_packets: (result as { task_packets?: unknown }).task_packets,
          clarification_questions: (result as { clarification_questions?: unknown })
            .clarification_questions,
          structure_route: result.structure_route,
          verification_outcome: result.verification_outcome,
          verification_report: result.verification_report,
          escalation_packet: (result as { escalation_packet?: unknown }).escalation_packet,
          cost_ledger_entries: result.cost_ledger_entries,
          api_brain: {
            escalation_count: (result as any).escalation_count ?? 0,
            packet: (result as any).api_brain_packet,
            output: (result as any).api_brain_output,
          },
        }
      } else if (workflowName === "engineering_physics_v1") {
        const prompt = String(inputData.user_prompt ?? inputData.prompt ?? "")
        if (!prompt.trim()) {
          return reply.status(422).send({
            detail: "engineering_physics_v1 requires input_data.user_prompt",
          })
        }
        const result = await physicsHarnessWorkflow.invoke({
          user_prompt: prompt,
          current_step: "intake",
        })
        const syn = result.synthesis_infer as { text?: string } | undefined
        output = {
          root_packet_id: result.root_packet_id,
          intake_infer: result.intake_infer,
          solve_request: result.solve_request,
          engineering_report: result.engineering_report,
          verification_outcome: result.verification_outcome,
          synthesis_infer: result.synthesis_infer,
          harness_error: result.harness_error,
          final_response: syn?.text ?? result.harness_error ?? "",
        }
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

  app.post("/v1/devplane/runs", async (request, reply) => {
    const parsed = devPlaneRunCreateSchema.safeParse(request.body)
    if (!parsed.success) {
      return reply.status(400).send({ detail: parsed.error.flatten() })
    }
    const backendRun = createBackendRun(parsed.data)
    void executeBackendRun(backendRun.run_id, {
      cfg,
      defaultModel,
      defaultProvider,
    }).catch((error) => {
      app.log.error(error)
    })
    return {
      run_id: backendRun.run_id,
      control_run_id: backendRun.control_run_id,
      status: backendRun.status,
      phase: backendRun.phase,
      summary: backendRun.summary,
      files_changed: backendRun.files_changed,
      verification_results: backendRun.verification_results,
      artifacts: backendRun.artifacts,
    }
  })

  app.get<{ Params: { id: string } }>(
    "/v1/devplane/runs/:id",
    async (request, reply) => {
      const backendRun = getBackendRun(request.params.id)
      if (!backendRun) {
        return reply.status(404).send({ detail: "run not found" })
      }
      return {
        run_id: backendRun.run_id,
        control_run_id: backendRun.control_run_id,
        status: backendRun.status,
        phase: backendRun.phase,
        summary: backendRun.summary,
        files_changed: backendRun.files_changed,
        verification_results: backendRun.verification_results,
        artifacts: backendRun.artifacts,
      }
    },
  )

  app.post<{ Params: { id: string } }>(
    "/v1/devplane/runs/:id/cancel",
    async (request, reply) => {
      const backendRun = markRunCancelled(request.params.id)
      if (!backendRun) {
        return reply.status(404).send({ detail: "run not found" })
      }
      return {
        run_id: backendRun.run_id,
        control_run_id: backendRun.control_run_id,
        status: backendRun.status,
        phase: backendRun.phase,
        summary: backendRun.summary,
        files_changed: backendRun.files_changed,
        verification_results: backendRun.verification_results,
        artifacts: backendRun.artifacts,
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
