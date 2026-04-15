import crypto from "node:crypto"
import { pathToFileURL } from "node:url"
import Fastify from "fastify"
import { z } from "zod"
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
import { OrchestrationEngine } from "./orchestration/engine.js"
import type { ChatMessage } from "./tools/wrkhrs.js"
import { createChatWorkflow } from "./workflow/graph.js"
import { createEngineeringWorkflow } from "./workflow/engineering-graph.js"
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
  "rag_retrieval",
  "tool_execution",
  "github_integration",
  "policy_validation",
  "devplane_code_task",
] as const

const providerSchema = z.enum([
  "anthropic",
  "copilot",
  "grok",
  "openai",
  "gemini",
  "ollama",
  "vllm",
  "huggingface",
  "hf",
  "hosted_api",
  "local_worker",
  "local",
  "swarm",
])

function withModelRouting(
  inputData: Record<string, unknown>,
  workflowConfig?: Record<string, unknown>,
): Record<string, unknown> | undefined {
  const existing = workflowConfig ?? {}
  const current =
    existing.model_routing &&
    typeof existing.model_routing === "object" &&
    !Array.isArray(existing.model_routing)
      ? (existing.model_routing as Record<string, unknown>)
      : {}
  const modelRouting: Record<string, unknown> = { ...current }

  if (typeof inputData.model === "string" && inputData.model.trim()) {
    modelRouting.model = inputData.model
  }
  if (typeof inputData.temperature === "number") {
    modelRouting.temperature = inputData.temperature
  }
  if (typeof inputData.max_tokens === "number") {
    modelRouting.max_tokens = inputData.max_tokens
  }
  if (typeof inputData.maxTokens === "number") {
    modelRouting.maxTokens = inputData.maxTokens
  }
  if (typeof inputData.provider === "string" && inputData.provider.trim()) {
    modelRouting.provider_preference = inputData.provider
  }
  if (
    typeof existing.provider_preference === "string" &&
    existing.provider_preference.trim() &&
    modelRouting.provider_preference === undefined
  ) {
    modelRouting.provider_preference = existing.provider_preference
  }

  if (Object.keys(modelRouting).length === 0) {
    return workflowConfig
  }
  return { ...existing, model_routing: modelRouting }
}

export function buildServer() {
  const cfg = loadConfig()
  const llm = new LLMManager(cfg)
  const omaTools = createWrkhrsOmaTools(cfg)
  const engine = new OrchestrationEngine(cfg, llm)
  const defaultModel = cfg.orchestrationDefaultModel
  const defaultProvider = cfg.orchestrationDefaultProvider

  function toTokenUsage(
    usage?: {
      prompt_tokens: number
      completion_tokens: number
    },
  ): { input_tokens: number; output_tokens: number } {
    return {
      input_tokens: usage?.prompt_tokens ?? 0,
      output_tokens: usage?.completion_tokens ?? 0,
    }
  }

  async function callApiBrain(packet: string): Promise<string> {
    if (!cfg.apiBrainEnabled) {
      return "API brain disabled."
    }
    const result = await engine.runDirectAgent({
      name: "api_brain",
      prompt: packet,
      systemPrompt:
        "You are the hosted API brain. Return a compact PLAN/REVIEW/DECISION/PATCH_GUIDANCE. " +
        "Do not ask questions. Do not include raw logs. Use only the provided packet.",
      model: cfg.apiBrainModel || defaultModel,
      provider: cfg.apiBrainProvider || defaultProvider,
      maxTurns: 4,
      toolNames: [],
    })
    return result.output
  }

  const chatWorkflow = createChatWorkflow(cfg, engine, callApiBrain)
  const engineeringWorkflow = createEngineeringWorkflow(cfg, engine, callApiBrain)

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
    provider: providerSchema.optional(),
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
      workflow_config: withModelRouting({
        model: body.model,
        temperature: body.temperature,
        max_tokens: body.max_tokens,
        provider: body.provider,
      }),
    })

    const content = (result.final_response ?? "").trim()
    if (!content) {
      return reply.status(502).send({
        detail: {
          error_code: "orchestrator_empty_response",
          message: "Orchestrator produced an empty final_response.",
          debug_hint:
            "Check wrkhrs-agent-platform logs for workflow execution errors and verify LLM_BACKEND is set to a real backend (not mock).",
        },
      })
    }

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
            content,
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
      if (!["ollama", "vllm", "huggingface", "hf", "mock", "none", "disabled"].includes(backend_type)) {
        return reply.status(400).send({
          detail: "Backend must be ollama, vllm, huggingface, hf, mock, none, or disabled",
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
    async (request, reply) => {
      const name = request.params.name
      if (name === "engineering_physics_v1") {
        return reply.status(410).send({
          detail:
            "engineering_physics_v1 was archived to ../server-local-archive/2026-04-08/server and is no longer part of the active orchestration surface.",
        })
      }
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
    if (workflowName === "engineering_physics_v1") {
      return reply.status(410).send({
        detail:
          "engineering_physics_v1 was archived to ../server-local-archive/2026-04-08/server and is no longer part of the active orchestration surface.",
      })
    }
    const id = crypto.randomUUID()
    const started = Date.now()
    createWorkflowRun(id, workflowName)

    try {
      let output: unknown

      if (workflowName === "wrkhrs_chat" || workflowName === "default") {
        const messages = (inputData.messages as ChatMessage[]) ?? [
          { role: "user", content: String(inputData.prompt ?? inputData.query ?? "") },
        ]
        const workflowConfig = withModelRouting(
          inputData,
          (body.workflow_config as Record<string, unknown> | undefined) ?? undefined,
        )
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
          engagement_mode: (workflowConfig as Record<string, unknown> | undefined)?.engagement_mode,
          engagement_mode_source: (workflowConfig as Record<string, unknown> | undefined)
            ?.engagement_mode_source,
          engagement_mode_confidence: (workflowConfig as Record<string, unknown> | undefined)
            ?.engagement_mode_confidence,
          engagement_mode_reasons: (workflowConfig as Record<string, unknown> | undefined)
            ?.engagement_mode_reasons,
          minimum_engagement_mode: (workflowConfig as Record<string, unknown> | undefined)
            ?.minimum_engagement_mode,
          pending_mode_change: (workflowConfig as Record<string, unknown> | undefined)
            ?.pending_mode_change,
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
        const workflowConfig = withModelRouting(
          inputData,
          (body.workflow_config as Record<string, unknown> | undefined) ?? undefined,
        )
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
          engagement_mode: inputData.engagement_mode as string | undefined,
          engagement_mode_source: inputData.engagement_mode_source as string | undefined,
          engagement_mode_confidence: inputData.engagement_mode_confidence as number | undefined,
          engagement_mode_reasons:
            (inputData.engagement_mode_reasons as string[] | undefined) ?? [],
          minimum_engagement_mode:
            (inputData.minimum_engagement_mode as string | undefined) ?? undefined,
          pending_mode_change:
            (inputData.pending_mode_change as Record<string, unknown> | undefined) ?? undefined,
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
            active_task_packet_ref: (result as { active_task_packet_ref?: unknown })
              .active_task_packet_ref,
            selected_executor: (result as { active_selected_executor?: unknown })
              .active_selected_executor,
            dossier_snapshot: (result as { dossier_snapshot?: unknown })
              .dossier_snapshot,
            engagement_mode: (result as { engagement_mode?: unknown }).engagement_mode,
            minimum_engagement_mode:
              (result as { minimum_engagement_mode?: unknown }).minimum_engagement_mode,
          },
          problem_brief: (result as { problem_brief?: unknown }).problem_brief,
          engineering_state: (result as { engineering_state?: unknown }).engineering_state,
          task_queue: (result as { task_queue?: unknown }).task_queue,
          task_packets: (result as { task_packets?: unknown }).task_packets,
          required_gates: (result as { required_gates?: unknown }).required_gates,
          ready_for_task_decomposition: (result as { ready_for_task_decomposition?: unknown })
            .ready_for_task_decomposition,
          clarification_questions: (result as { clarification_questions?: unknown })
            .clarification_questions,
          verification_outcome: result.verification_outcome,
          verification_report: result.verification_report,
          escalation_packet: (result as { escalation_packet?: unknown }).escalation_packet,
          engagement_mode: (result as { engagement_mode?: unknown }).engagement_mode,
          engagement_mode_source:
            (result as { engagement_mode_source?: unknown }).engagement_mode_source,
          engagement_mode_confidence:
            (result as { engagement_mode_confidence?: unknown }).engagement_mode_confidence,
          engagement_mode_reasons:
            (result as { engagement_mode_reasons?: unknown }).engagement_mode_reasons,
          minimum_engagement_mode:
            (result as { minimum_engagement_mode?: unknown }).minimum_engagement_mode,
          pending_mode_change:
            (result as { pending_mode_change?: unknown }).pending_mode_change,
          lifecycle_reason: (result as { lifecycle_reason?: unknown }).lifecycle_reason,
          lifecycle_detail: (result as { lifecycle_detail?: unknown }).lifecycle_detail,
          cost_ledger_entries: result.cost_ledger_entries,
          api_brain: {
            escalation_count: (result as any).escalation_count ?? 0,
            packet: (result as any).api_brain_packet,
            output: (result as any).api_brain_output,
          },
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
    }).catch((error) => {
      app.log.error(error)
    })
    return {
      run_id: backendRun.run_id,
      control_run_id: backendRun.control_run_id,
      status: backendRun.status,
      phase: backendRun.phase,
      engagement_mode: backendRun.engagement_mode,
      engagement_mode_source: backendRun.engagement_mode_source,
      engagement_mode_confidence: backendRun.engagement_mode_confidence,
      engagement_mode_reasons: backendRun.engagement_mode_reasons,
      minimum_engagement_mode: backendRun.minimum_engagement_mode,
      pending_mode_change: backendRun.pending_mode_change,
      lifecycle_reason: backendRun.lifecycle_reason,
      lifecycle_detail: backendRun.lifecycle_detail,
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
        engagement_mode: backendRun.engagement_mode,
        engagement_mode_source: backendRun.engagement_mode_source,
        engagement_mode_confidence: backendRun.engagement_mode_confidence,
        engagement_mode_reasons: backendRun.engagement_mode_reasons,
        minimum_engagement_mode: backendRun.minimum_engagement_mode,
        pending_mode_change: backendRun.pending_mode_change,
        lifecycle_reason: backendRun.lifecycle_reason,
        lifecycle_detail: backendRun.lifecycle_detail,
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
        engagement_mode: backendRun.engagement_mode,
        engagement_mode_source: backendRun.engagement_mode_source,
        engagement_mode_confidence: backendRun.engagement_mode_confidence,
        engagement_mode_reasons: backendRun.engagement_mode_reasons,
        minimum_engagement_mode: backendRun.minimum_engagement_mode,
        pending_mode_change: backendRun.pending_mode_change,
        lifecycle_reason: backendRun.lifecycle_reason,
        lifecycle_detail: backendRun.lifecycle_detail,
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
      provider: providerSchema.optional(),
      systemPrompt: z.string().optional(),
      tools: z.array(z.string()).optional(),
      maxTurns: z.number().optional(),
      maxTokens: z.number().optional(),
      max_tokens: z.number().optional(),
      temperature: z.number().optional(),
    }),
    prompt: z.string(),
  })

  app.post("/v1/agents/run", async (request, reply) => {
    const parsed = agentRunBody.safeParse(request.body)
    if (!parsed.success) {
      return reply.status(400).send({ detail: parsed.error.flatten() })
    }
    const { agent: agentSpec, prompt } = parsed.data
    const result = await engine.runDirectAgent({
      name: agentSpec.name,
      prompt,
      systemPrompt: agentSpec.systemPrompt,
      model: agentSpec.model,
      provider: agentSpec.provider,
      extraTools: omaTools,
      toolNames: agentSpec.tools ?? ["search_knowledge_base", "get_domain_data"],
      maxTurns: agentSpec.maxTurns ?? 8,
      maxTokens: agentSpec.maxTokens ?? agentSpec.max_tokens,
      temperature: agentSpec.temperature,
    })
    return {
      success: result.success,
      output: result.output,
      tokenUsage: toTokenUsage(result.usage),
      toolCalls: result.toolCalls ?? [],
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
        provider: providerSchema.optional(),
        systemPrompt: z.string().optional(),
        tools: z.array(z.string()).optional(),
        maxTurns: z.number().optional(),
        maxTokens: z.number().optional(),
        max_tokens: z.number().optional(),
        temperature: z.number().optional(),
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
    try {
      const result = await engine.runGoalTeam({
        teamName: `${body.team.name}-${crypto.randomUUID()}`,
        goal: body.goal,
        sharedMemory: body.team.sharedMemory ?? true,
        maxConcurrency: body.team.maxConcurrency,
        extraTools: omaTools,
        agents: body.team.agents.map((agent) => ({
          name: agent.name,
          model: agent.model,
          provider: agent.provider,
          systemPrompt: agent.systemPrompt,
          toolNames: agent.tools ?? ["search_knowledge_base", "get_domain_data"],
          maxTurns: agent.maxTurns ?? 6,
          maxTokens: agent.maxTokens ?? agent.max_tokens,
          temperature: agent.temperature,
        })),
      })
      return {
        success: result.success,
        totalTokenUsage: toTokenUsage(result.usage),
        agentResults: result.agentResults ?? {},
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
    try {
      const fallbackAgent = body.team.agents[0]
      if (!fallbackAgent) {
        return reply.status(400).send({
          detail: "team.agents must include at least one agent for /v1/tasks/run",
        })
      }

      const agentByName = new Map(body.team.agents.map((agent) => [agent.name, agent]))
      const result = await engine.runGovernedTaskGraph({
        teamName: `${body.team.name}-tasks-${crypto.randomUUID()}`,
        sharedMemory: body.team.sharedMemory ?? true,
        maxConcurrency: body.team.maxConcurrency,
        extraTools: omaTools,
        tasks: body.tasks.map((task) => {
          const assignee = task.assignee ?? fallbackAgent.name
          const agent = agentByName.get(assignee)
          if (!agent) {
            throw new Error(`Task assignee ${assignee} is not defined in team.agents.`)
          }
          return {
            title: task.title,
            description: task.description,
            assignee,
            dependsOn: task.dependsOn,
            systemPrompt: agent.systemPrompt ?? "",
            toolNames: agent.tools ?? ["search_knowledge_base", "get_domain_data"],
            maxTurns: agent.maxTurns ?? 6,
            model: agent.model,
            provider: agent.provider,
            providerPreference: agent.provider,
            maxTokens: agent.maxTokens ?? agent.max_tokens,
            temperature: agent.temperature,
          }
        }),
      })
      return {
        success: result.success,
        totalTokenUsage: toTokenUsage(result.usage),
        agentResults: result.agentResults ?? {},
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
