import {
  OpenMultiAgent,
  type AgentRunResult as OmaAgentRunResult,
  type SupportedProvider,
  type ToolCallRecord,
  type ToolDefinition,
} from "@server/open-multi-agent"
import type { PlatformConfig } from "../config.js"
import { LLMManager } from "../llm/manager.js"
import { postInferMultimodal } from "../llm/model-runtime-client.js"
import type { ChatMessage } from "../tools/wrkhrs.js"
import {
  ClawCodeExecutor,
  type ClawCodeExecutionInput,
  type OrchestrationArtifact,
} from "./claw-code-executor.js"
import {
  resolveExecutorRuntime,
  resolveMergedOmaRoute,
  type ExecutorRuntime,
} from "./runtime-router.js"

export interface EngineUsage {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  latency_ms?: number
}

export interface EngineRunResult {
  runtime: ExecutorRuntime | "mock"
  success: boolean
  output: string
  model?: string
  usage?: EngineUsage
  structuredOutput?: Record<string, unknown>
  agentOutputs?: Record<string, string>
  agentResults?: Record<string, OmaAgentRunResult>
  toolCalls?: ToolCallRecord[]
  artifacts?: OrchestrationArtifact[]
}

export interface DirectAgentInput {
  name: string
  prompt: string
  systemPrompt?: string
  extraTools?: readonly ToolDefinition[]
  toolNames?: readonly string[]
  maxTurns?: number
  maxTokens?: number
  temperature?: number
  model?: string
  provider?: string
  providerPreference?: string
  baseURL?: string
  apiKey?: string
}

export interface GoalTeamAgentDefinition {
  name: string
  model?: string
  provider?: string
  providerPreference?: string
  baseURL?: string
  apiKey?: string
  systemPrompt?: string
  toolNames?: readonly string[]
  maxTurns?: number
  maxTokens?: number
  temperature?: number
}

export interface GoalTeamInput {
  teamName: string
  goal: string
  agents: GoalTeamAgentDefinition[]
  extraTools?: readonly ToolDefinition[]
  sharedMemory?: boolean
  maxConcurrency?: number
}

export interface GovernedTaskDefinition {
  title: string
  description: string
  assignee: string
  systemPrompt: string
  dependsOn?: string[]
  toolNames?: readonly string[]
  maxTurns?: number
  maxTokens?: number
  temperature?: number
  model?: string
  provider?: string
  providerPreference?: string
  baseURL?: string
  apiKey?: string
}

export interface GovernedTaskGraphInput {
  teamName: string
  tasks: GovernedTaskDefinition[]
  extraTools?: readonly ToolDefinition[]
  sharedMemory?: boolean
  maxConcurrency?: number
}

export interface GovernedEngineeringInput {
  selectedExecutor: string
  title: string
  prompt: string
  systemPrompt: string
  workspaceRoot?: string
  extraTools?: readonly ToolDefinition[]
  toolNames?: readonly string[]
  taskGraph?: GovernedTaskDefinition[]
  packet?: Record<string, unknown>
  claw?: Partial<ClawCodeExecutionInput>
  model?: string
  provider?: string
  providerPreference?: string
  baseURL?: string
  apiKey?: string
}

function supportedProviderFromHint(value: string | undefined): SupportedProvider | undefined {
  switch (value?.trim().toLowerCase()) {
    case "anthropic":
    case "copilot":
    case "grok":
    case "openai":
    case "gemini":
    case "ollama":
      return value.trim().toLowerCase() as SupportedProvider
    default:
      return undefined
  }
}

function transcriptFromMessages(messages: ChatMessage[]): string {
  return messages
    .map((message) => `${message.role.toUpperCase()}: ${message.content}`)
    .join("\n\n")
}

function usageFromTokenCounts(
  promptTokens: number,
  completionTokens: number,
  latencyMs?: number,
): EngineUsage {
  return {
    prompt_tokens: promptTokens,
    completion_tokens: completionTokens,
    total_tokens: promptTokens + completionTokens,
    latency_ms: latencyMs,
  }
}

function toStructuredRecord(value: unknown): Record<string, unknown> | undefined {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>
  }
  return undefined
}

function toTokenUsage(usage: EngineUsage): { input_tokens: number; output_tokens: number } {
  return {
    input_tokens: usage.prompt_tokens,
    output_tokens: usage.completion_tokens,
  }
}

function sumUsage(values: EngineUsage[]): EngineUsage {
  return values.reduce(
    (acc, item) => ({
      prompt_tokens: acc.prompt_tokens + item.prompt_tokens,
      completion_tokens: acc.completion_tokens + item.completion_tokens,
      total_tokens: acc.total_tokens + item.total_tokens,
      latency_ms:
        acc.latency_ms === undefined && item.latency_ms === undefined
          ? undefined
          : (acc.latency_ms ?? 0) + (item.latency_ms ?? 0),
    }),
    {
      prompt_tokens: 0,
      completion_tokens: 0,
      total_tokens: 0,
      latency_ms: 0,
    } satisfies EngineUsage,
  )
}

function agentResultsToOutputs(
  agentResults: Record<string, OmaAgentRunResult>,
): Record<string, string> {
  return Object.fromEntries(
    Object.entries(agentResults).map(([name, result]) => [name, result.output]),
  )
}

export class OrchestrationEngine {
  private readonly claw: ClawCodeExecutor

  constructor(
    private readonly cfg: PlatformConfig,
    private readonly llm: LLMManager,
  ) {
    this.claw = new ClawCodeExecutor(cfg)
  }

  private createOrchestration(input: {
    model?: string
    provider?: string
    providerPreference?: string
    baseURL?: string
    apiKey?: string
    extraTools?: readonly ToolDefinition[]
  }): OpenMultiAgent {
    const route = resolveMergedOmaRoute(this.cfg, {
      model: input.model,
      provider: supportedProviderFromHint(input.provider),
      providerPreference: input.providerPreference ?? input.provider,
      baseURL: input.baseURL,
      apiKey: input.apiKey,
    })
    return new OpenMultiAgent({
      defaultModel: route.model,
      defaultProvider: route.provider,
      enableBuiltInTools: false,
      extraTools: input.extraTools,
      ...(route.baseURL ? { defaultBaseURL: route.baseURL } : {}),
      ...(route.apiKey ? { defaultApiKey: route.apiKey } : {}),
      ...(route.maxTokenBudget ? { maxTokenBudget: route.maxTokenBudget } : {}),
    } as any)
  }

  private async runMockAgent(input: DirectAgentInput): Promise<EngineRunResult> {
    const result = await this.llm.chatCompletion(
      [
        ...(input.systemPrompt
          ? [{ role: "system" as const, content: input.systemPrompt }]
          : []),
        { role: "user" as const, content: input.prompt },
      ],
      {
        temperature: input.temperature,
        max_tokens: input.maxTokens,
      },
    )
    const output = result.choices[0]?.message?.content ?? "No response generated"
    const usage = usageFromTokenCounts(
      result.usage.prompt_tokens,
      result.usage.completion_tokens,
    )
    const agentResult: OmaAgentRunResult = {
      success: true,
      output,
      messages: [],
      tokenUsage: toTokenUsage(usage),
      toolCalls: [],
    }
    return {
      runtime: "mock",
      success: true,
      output,
      model: result.model,
      usage,
      toolCalls: [],
      agentResults: { [input.name]: agentResult },
      agentOutputs: { [input.name]: output },
    }
  }

  async runDirectAgent(input: DirectAgentInput): Promise<EngineRunResult> {
    const route = resolveMergedOmaRoute(this.cfg, {
      model: input.model,
      provider: supportedProviderFromHint(input.provider),
      providerPreference: input.providerPreference ?? input.provider,
      baseURL: input.baseURL,
      apiKey: input.apiKey,
    })

    if (route.transport === "mock") {
      return this.runMockAgent(input)
    }

    const orchestration = this.createOrchestration({
      model: input.model,
      provider: input.provider,
      providerPreference: input.providerPreference,
      baseURL: input.baseURL,
      apiKey: input.apiKey,
      extraTools: input.extraTools,
    })
    const result = await orchestration.runAgent(
      {
        name: input.name,
        model: route.model,
        provider: route.provider,
        ...(route.apiKey ? { apiKey: route.apiKey } : {}),
        ...(route.baseURL ? { baseURL: route.baseURL } : {}),
        systemPrompt: input.systemPrompt,
        tools: input.toolNames,
        maxTurns: input.maxTurns ?? 6,
        maxTokens: input.maxTokens,
        temperature: input.temperature,
        ...(route.maxTokenBudget ? { maxTokenBudget: route.maxTokenBudget } : {}),
      } as any,
      input.prompt,
    )

    return {
      runtime: route.runtime,
      success: result.success,
      output: result.output,
      model: route.model,
      usage: usageFromTokenCounts(
        result.tokenUsage.input_tokens,
        result.tokenUsage.output_tokens,
      ),
      structuredOutput: toStructuredRecord((result as any).structured),
      toolCalls: result.toolCalls,
      agentResults: { [input.name]: result },
      agentOutputs: { [input.name]: result.output },
    }
  }

  async runGoalTeam(input: GoalTeamInput): Promise<EngineRunResult> {
    if (input.agents.length === 0) {
      throw new Error("runGoalTeam requires at least one team agent.")
    }

    const defaultRoute = resolveMergedOmaRoute(this.cfg)
    if (defaultRoute.transport === "mock") {
      const agentResults: Record<string, OmaAgentRunResult> = {}
      const usages: EngineUsage[] = []
      for (const agent of input.agents) {
        const result = await this.runDirectAgent({
          name: agent.name,
          prompt: input.goal,
          systemPrompt: agent.systemPrompt,
          extraTools: input.extraTools,
          toolNames: agent.toolNames,
          maxTurns: agent.maxTurns,
          maxTokens: agent.maxTokens,
          temperature: agent.temperature,
          model: agent.model,
          provider: agent.provider,
          providerPreference: agent.providerPreference,
          baseURL: agent.baseURL,
          apiKey: agent.apiKey,
        })
        const agentResult = result.agentResults?.[agent.name]
        if (agentResult) {
          agentResults[agent.name] = agentResult
        }
        if (result.usage) {
          usages.push(result.usage)
        }
      }
      const output =
        agentResults[input.agents[input.agents.length - 1]?.name]?.output ??
        Object.values(agentResults)[0]?.output ??
        ""
      return {
        runtime: "mock",
        success: true,
        output,
        model: "mock-llm",
        usage: sumUsage(usages),
        agentResults,
        agentOutputs: agentResultsToOutputs(agentResults),
      }
    }

    const orchestration = this.createOrchestration({
      extraTools: input.extraTools,
    })
    const team = orchestration.createTeam(input.teamName, {
      name: input.teamName,
      sharedMemory: input.sharedMemory ?? true,
      maxConcurrency: input.maxConcurrency,
      agents: input.agents.map((agent) => {
        const route = resolveMergedOmaRoute(this.cfg, {
          model: agent.model,
          provider: supportedProviderFromHint(agent.provider),
          providerPreference: agent.providerPreference ?? agent.provider,
          baseURL: agent.baseURL,
          apiKey: agent.apiKey,
        })
        return {
          name: agent.name,
          model: route.model,
          provider: route.provider,
          ...(route.apiKey ? { apiKey: route.apiKey } : {}),
          ...(route.baseURL ? { baseURL: route.baseURL } : {}),
          systemPrompt: agent.systemPrompt,
          tools: agent.toolNames,
          maxTurns: agent.maxTurns ?? 6,
          maxTokens: agent.maxTokens,
          temperature: agent.temperature,
          ...(route.maxTokenBudget ? { maxTokenBudget: route.maxTokenBudget } : {}),
        } as any
      }),
    })
    const result = await orchestration.runTeam(team, input.goal)
    const agentResults = Object.fromEntries(result.agentResults) as Record<
      string,
      OmaAgentRunResult
    >
    const output =
      agentResults.coordinator?.output ??
      Object.values(agentResults)[0]?.output ??
      ""
    return {
      runtime: defaultRoute.runtime,
      success: result.success,
      output,
      model: defaultRoute.model,
      usage: usageFromTokenCounts(
        result.totalTokenUsage.input_tokens,
        result.totalTokenUsage.output_tokens,
      ),
      agentResults,
      agentOutputs: agentResultsToOutputs(agentResults),
    }
  }

  async runSimpleChat(input: {
    messages: ChatMessage[]
    systemPrompt?: string
    extraTools?: readonly ToolDefinition[]
    toolNames?: readonly string[]
    maxTurns?: number
    maxTokens?: number
    temperature?: number
    model?: string
    provider?: string
    providerPreference?: string
    baseURL?: string
    apiKey?: string
  }): Promise<EngineRunResult> {
    return this.runDirectAgent({
      name: "wrkhrs_chat",
      prompt: transcriptFromMessages(input.messages),
      systemPrompt: input.systemPrompt,
      extraTools: input.extraTools,
      toolNames: input.toolNames,
      maxTurns: input.maxTurns,
      maxTokens: input.maxTokens,
      temperature: input.temperature,
      model: input.model,
      provider: input.provider,
      providerPreference: input.providerPreference,
      baseURL: input.baseURL,
      apiKey: input.apiKey,
    })
  }

  async runGovernedTaskGraph(input: GovernedTaskGraphInput): Promise<EngineRunResult> {
    if (input.tasks.length === 0) {
      throw new Error("runGovernedTaskGraph requires at least one explicit task.")
    }

    const firstTask = input.tasks[0]
    const route = resolveMergedOmaRoute(this.cfg, {
      model: firstTask?.model,
      provider: supportedProviderFromHint(firstTask?.provider),
      providerPreference: firstTask?.providerPreference ?? firstTask?.provider,
      baseURL: firstTask?.baseURL,
      apiKey: firstTask?.apiKey,
    })

    if (route.transport === "mock") {
      const agentResults: Record<string, OmaAgentRunResult> = {}
      let finalOutput = ""
      const usages: EngineUsage[] = []
      for (const task of input.tasks) {
        const result = await this.llm.chatCompletion(
          [
            { role: "system", content: task.systemPrompt },
            { role: "user", content: task.description },
          ],
          {
            temperature: task.temperature,
            max_tokens: task.maxTokens,
          },
        )
        finalOutput = result.choices[0]?.message?.content ?? "No response generated"
        const usage = usageFromTokenCounts(
          result.usage.prompt_tokens,
          result.usage.completion_tokens,
        )
        usages.push(usage)
        agentResults[task.assignee] = {
          success: true,
          output: finalOutput,
          messages: [],
          tokenUsage: toTokenUsage(usage),
          toolCalls: [],
        }
      }
      return {
        runtime: "mock",
        success: true,
        output: finalOutput,
        model: "mock-llm",
        usage: sumUsage(usages),
        agentResults,
        agentOutputs: agentResultsToOutputs(agentResults),
      }
    }

    const orchestration = this.createOrchestration({
      model: firstTask?.model,
      provider: firstTask?.provider,
      providerPreference: firstTask?.providerPreference,
      baseURL: firstTask?.baseURL,
      apiKey: firstTask?.apiKey,
      extraTools: input.extraTools,
    })

    const agentConfigs = new Map<string, GovernedTaskDefinition>()
    for (const task of input.tasks) {
      if (!agentConfigs.has(task.assignee)) {
        agentConfigs.set(task.assignee, task)
      }
    }

    const team = orchestration.createTeam(input.teamName, {
      name: input.teamName,
      sharedMemory: input.sharedMemory ?? false,
      maxConcurrency: input.maxConcurrency ?? Math.min(input.tasks.length, 2),
      agents: Array.from(agentConfigs.entries()).map(([assignee, task]) => {
        const agentRoute = resolveMergedOmaRoute(this.cfg, {
          model: task.model,
          provider: supportedProviderFromHint(task.provider),
          providerPreference: task.providerPreference ?? task.provider,
          baseURL: task.baseURL,
          apiKey: task.apiKey,
        })
        return {
          name: assignee,
          model: agentRoute.model,
          provider: agentRoute.provider,
          baseURL: agentRoute.baseURL,
          apiKey: agentRoute.apiKey,
          systemPrompt: task.systemPrompt,
          tools: task.toolNames,
          maxTurns: task.maxTurns ?? 8,
          maxTokens: task.maxTokens,
          temperature: task.temperature,
          maxTokenBudget: agentRoute.maxTokenBudget,
        }
      }),
    })

    const result = await orchestration.runTasks(
      team,
      input.tasks.map((task) => ({
        title: task.title,
        description: task.description,
        assignee: task.assignee,
        dependsOn: task.dependsOn,
      })),
    )

    const agentResults = Object.fromEntries(result.agentResults) as Record<
      string,
      OmaAgentRunResult
    >
    const agentOutputs = agentResultsToOutputs(agentResults)
    const finalOutput =
      agentOutputs[input.tasks[input.tasks.length - 1]?.assignee] ??
      Object.values(agentOutputs)[0] ??
      ""

    return {
      runtime: route.runtime,
      success: result.success,
      output: finalOutput,
      model: route.model,
      usage: usageFromTokenCounts(
        result.totalTokenUsage.input_tokens,
        result.totalTokenUsage.output_tokens,
      ),
      agentResults,
      agentOutputs,
    }
  }

  async runGovernedEngineering(input: GovernedEngineeringInput): Promise<EngineRunResult> {
    const runtime = resolveExecutorRuntime(input.selectedExecutor)
    if (!runtime) {
      throw new Error(`Unsupported executor runtime for ${input.selectedExecutor}`)
    }

    if (runtime === "merged_oma") {
      return this.runGovernedTaskGraph({
        teamName: `governed-${input.selectedExecutor}`,
        extraTools: input.extraTools,
        tasks:
          input.taskGraph ??
          [
            {
              title: input.title,
              description: input.prompt,
              assignee: input.selectedExecutor,
              systemPrompt: input.systemPrompt,
              toolNames: input.toolNames,
              model: input.model,
              provider: input.provider,
              providerPreference: input.providerPreference,
              baseURL: input.baseURL,
              apiKey: input.apiKey,
            },
          ],
      })
    }

    if (runtime === "claw_code") {
      if (!input.workspaceRoot) {
        throw new Error("coding_model requires a governed workspaceRoot for Claw execution.")
      }
      const clawInput = input.claw
      if (!clawInput) {
        throw new Error("coding_model requires translated Claw execution input.")
      }
      const result = await this.claw.execute({
        workspaceRoot: input.workspaceRoot,
        objective: clawInput.objective ?? input.title,
        scope: clawInput.scope ?? input.title,
        repo: clawInput.repo ?? pathBasename(input.workspaceRoot),
        branchPolicy: clawInput.branchPolicy ?? "governed worktree only",
        acceptanceTests: clawInput.acceptanceTests ?? [],
        commitPolicy: clawInput.commitPolicy ?? "leave changes unstaged for control-plane review",
        reportingContract:
          clawInput.reportingContract ??
          "Persist output through Claw manifest/output files and summarize file changes only.",
        escalationPolicy:
          clawInput.escalationPolicy ??
          "Stop on destructive ambiguity and record blockers in the manifest.",
        prompt: clawInput.prompt ?? input.prompt,
        agentName: clawInput.agentName,
        model: clawInput.model ?? this.cfg.clawCodeModel,
      })
      return {
        runtime,
        success: true,
        output: result.output,
        artifacts: result.artifacts,
      }
    }

    if (runtime === "model_runtime_multimodal") {
      if (!input.packet) {
        throw new Error("multimodal_model requires a governed task packet.")
      }
      const response = await postInferMultimodal(this.cfg, input.packet)
      return {
        runtime,
        success: true,
        output: response.text ?? "Structured multimodal extraction complete.",
        model: response.model_id_resolved,
        usage: {
          prompt_tokens: response.usage.prompt_tokens,
          completion_tokens: response.usage.completion_tokens,
          total_tokens: response.usage.prompt_tokens + response.usage.completion_tokens,
          latency_ms: response.usage.latency_ms,
        },
        structuredOutput: response.structured_output ?? {},
      }
    }

    return {
      runtime,
      success: true,
      output:
        "Deterministic validator selected as the active executor; execution is deferred to verification.",
    }
  }
}

function pathBasename(value: string): string {
  const normalized = value.replace(/\/$/, "")
  const parts = normalized.split("/")
  return parts[parts.length - 1] || normalized
}
