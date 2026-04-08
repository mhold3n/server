/**
 * Engineering-governed LangGraph workflow.
 *
 * The workflow no longer treats raw task_packet/chat state as authoritative.
 * Instead it routes all strict-engineering runs through the control-plane
 * intake bridge, which is responsible for:
 * - drafting/updating `problem_brief`
 * - deriving `engineering_state`
 * - blocking decomposition until gates are satisfied
 * - emitting `task_queue` / `task_packet` artifacts only when ready
 */

import { randomUUID } from "node:crypto"
import { Annotation, END, START, StateGraph } from "@langchain/langgraph"
import type { PlatformConfig } from "../config.js"
import { LLMBackendError, LLMManager } from "../llm/manager.js"
import type { ChatMessage } from "../tools/wrkhrs.js"
import { analyzeRequest, buildGatherContext } from "./graph.js"

export const EngineeringWorkflowAnnotation = Annotation.Root({
  messages: Annotation<ChatMessage[]>(),
  current_step: Annotation<string>(),
  tools_needed: Annotation<string[]>(),
  rag_results: Annotation<string | undefined>(),
  asr_results: Annotation<string | undefined>(),
  required_tool_results: Annotation<unknown[] | undefined>(),
  tool_results: Annotation<Record<string, string>>({
    reducer: (left, right) => ({ ...left, ...right }),
    default: () => ({}),
  }),
  workflow_config: Annotation<Record<string, unknown> | undefined>(),
  request_context: Annotation<Record<string, unknown> | undefined>(),
  escalation_count: Annotation<number>({
    reducer: (_left, right) => right,
    default: () => 0,
  }),
  api_brain_packet: Annotation<string | undefined>(),
  api_brain_output: Annotation<string | undefined>(),
  final_response: Annotation<string | undefined>(),
  run_id: Annotation<string | undefined>(),
  task_id: Annotation<string | undefined>(),
  dossier_id: Annotation<string | undefined>(),
  task_plan: Annotation<Record<string, unknown> | undefined>(),
  project_context: Annotation<Record<string, unknown> | undefined>(),
  engineering_session_id: Annotation<string | undefined>(),
  active_task_packet_id: Annotation<string | undefined>(),
  task_packet: Annotation<Record<string, unknown> | undefined>(),
  task_queue: Annotation<Record<string, unknown> | undefined>(),
  task_packets: Annotation<Record<string, unknown>[]>({
    reducer: (_left, right) => right,
    default: () => [],
  }),
  problem_brief: Annotation<Record<string, unknown> | undefined>(),
  problem_brief_ref: Annotation<string | undefined>(),
  engineering_state: Annotation<Record<string, unknown> | undefined>(),
  engineering_state_ref: Annotation<string | undefined>(),
  clarification_questions: Annotation<string[]>({
    reducer: (_left, right) => right,
    default: () => [],
  }),
  structure_route: Annotation<Record<string, unknown> | undefined>(),
  verification_outcome: Annotation<string | undefined>(),
  verification_report: Annotation<Record<string, unknown> | undefined>(),
  escalation_packet: Annotation<Record<string, unknown> | undefined>(),
  cost_ledger_entries: Annotation<Record<string, unknown>[]>({
    reducer: (left, right) => [...left, ...right],
    default: () => [],
  }),
  dossier_snapshot: Annotation<Record<string, unknown> | undefined>(),
})

export type EngineeringWorkflowStateType = typeof EngineeringWorkflowAnnotation.State

function latestUserContent(messages: ChatMessage[]): string {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (message?.role === "user") {
      return message.content
    }
  }
  return messages[messages.length - 1]?.content ?? ""
}

async function postControlPlane(
  cfg: PlatformConfig,
  path: string,
  payload: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const base = cfg.orchestratorApiUrl?.replace(/\/$/, "") ?? ""
  if (!base) {
    return { error: true, reason: "orchestrator_api_url_unset" }
  }
  const res = await fetch(`${base}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    return {
      error: true,
      status: res.status,
      body: await res.text().catch(() => ""),
    }
  }
  return (await res.json()) as Record<string, unknown>
}

async function classifyViaControlPlane(
  cfg: PlatformConfig,
  userInput: string,
  requestId: string,
): Promise<Record<string, unknown>> {
  return postControlPlane(cfg, "/api/control-plane/structure/classify", {
    user_input: userInput,
    request_id: requestId,
  })
}

async function fetchDevPlaneDossier(
  cfg: PlatformConfig,
  taskId: string,
): Promise<Record<string, unknown> | undefined> {
  const base = cfg.orchestratorApiUrl?.replace(/\/$/, "") ?? ""
  if (!base || !taskId) {
    return undefined
  }
  const url = `${base}/api/dev/tasks/${encodeURIComponent(taskId)}/dossier`
  const res = await fetch(url, { method: "GET" })
  if (!res.ok) {
    return { error: true, status: res.status, body: await res.text() }
  }
  return (await res.json()) as Record<string, unknown>
}

async function persistRunEvent(
  cfg: PlatformConfig,
  state: EngineeringWorkflowStateType,
  event: {
    message: string
    details: Record<string, unknown>
    artifacts: Array<Record<string, unknown>>
  },
): Promise<void> {
  const base = cfg.orchestratorApiUrl?.replace(/\/$/, "") ?? ""
  const runId = state.run_id
  if (!base || !runId || event.artifacts.length === 0) {
    return
  }
  const body = {
    message: event.message,
    details: event.details,
    cost_ledger: state.cost_ledger_entries ?? [],
    artifacts: event.artifacts,
  }
  const url = `${base}/api/dev/runs/${encodeURIComponent(runId)}/events`
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    console.warn("persistRunEvent failed", res.status, await res.text().catch(() => ""))
  }
}

function typedArtifact(
  artifactType: string,
  payload: Record<string, unknown>,
  inputRefs: string[],
  component: string,
): Record<string, unknown> {
  const artifactId =
    typeof payload.problem_brief_id === "string"
      ? payload.problem_brief_id
      : typeof payload.engineering_state_id === "string"
        ? payload.engineering_state_id
        : typeof payload.task_queue_id === "string"
          ? payload.task_queue_id
          : typeof payload.task_packet_id === "string"
            ? payload.task_packet_id
            : typeof payload.verification_report_id === "string"
              ? payload.verification_report_id
              : typeof payload.escalation_packet_id === "string"
                ? payload.escalation_packet_id
                : randomUUID()
  return {
    artifact_id: artifactId,
    artifact_type: artifactType,
    schema_version: String(payload.schema_version ?? "1.0.0"),
    artifact_status: "ACTIVE",
    validation_state: "VALID",
    producer: {
      component,
      executor: "local_general_model",
    },
    input_artifact_refs: inputRefs,
    supersedes: [],
    payload,
  }
}

function intakeEngineering(): Partial<EngineeringWorkflowStateType> {
  return {
    current_step: "engineering_intake",
  }
}

function buildEngineeringIntake(cfg: PlatformConfig) {
  return async function engineeringIntake(
    state: EngineeringWorkflowStateType,
  ): Promise<Partial<EngineeringWorkflowStateType>> {
    const dossierSnapshot =
      typeof state.task_id === "string" && state.task_id.length > 0
        ? await fetchDevPlaneDossier(cfg, state.task_id)
        : undefined
    const intake = await postControlPlane(cfg, "/api/control-plane/engineering/intake", {
      user_input: latestUserContent(state.messages),
      messages: state.messages,
      context: state.request_context,
      session_id: state.engineering_session_id,
      task_packet: state.task_packet,
      task_plan: state.task_plan,
      project_context: state.project_context,
    })

    if (intake.error === true) {
      const finalResponse = `Engineering intake failed: ${String(intake.body ?? intake.reason ?? "unknown error")}`
      return {
        dossier_snapshot: dossierSnapshot,
        final_response: finalResponse,
        verification_outcome: "FAILED",
        current_step: "complete",
      }
    }

    const clarificationQuestions = Array.isArray(intake.clarification_questions)
      ? (intake.clarification_questions as string[])
      : []
    const taskPackets = Array.isArray(intake.task_packets)
      ? (intake.task_packets as Record<string, unknown>[])
      : []
    const activeTaskPacket =
      taskPackets.find((packet) => packet.task_type !== "VALIDATION") ?? taskPackets[0]
    const activeTaskPacketId = activeTaskPacket?.task_packet_id
    const status = String(intake.status ?? "")

    if (status === "CLARIFICATION_REQUIRED") {
      return {
        dossier_snapshot: dossierSnapshot,
        engineering_session_id: intake.engineering_session_id as string | undefined,
        problem_brief: intake.problem_brief as Record<string, unknown> | undefined,
        problem_brief_ref: intake.problem_brief_ref as string | undefined,
        clarification_questions: clarificationQuestions,
        final_response:
          `Engineering clarification required:\n- ${clarificationQuestions.join("\n- ")}`,
        verification_outcome: "CLARIFICATION_REQUIRED",
        current_step: "complete",
      }
    }

    const problemBrief = intake.problem_brief as Record<string, unknown> | undefined
    const engineeringState = intake.engineering_state as Record<string, unknown> | undefined
    const taskQueue = intake.task_queue as Record<string, unknown> | undefined

    if (problemBrief && engineeringState) {
      const artifacts: Array<Record<string, unknown>> = [
        typedArtifact(
          "PROBLEM_BRIEF",
          problemBrief,
          [],
          "agent_platform.engineering_graph.intake",
        ),
        typedArtifact(
          "ENGINEERING_STATE",
          engineeringState,
          [String(intake.problem_brief_ref ?? "")].filter(Boolean),
          "agent_platform.engineering_graph.intake",
        ),
      ]
      if (taskQueue) {
        artifacts.push(
          typedArtifact(
            "TASK_QUEUE",
            taskQueue,
            [String(intake.problem_brief_ref ?? ""), String(intake.engineering_state_ref ?? "")].filter(Boolean),
            "agent_platform.engineering_graph.intake",
          ),
        )
      }
      for (const packet of taskPackets) {
        const inputRefs = Array.isArray(packet.input_artifact_refs)
          ? (packet.input_artifact_refs as string[])
          : []
        artifacts.push(
          typedArtifact(
            "TASK_PACKET",
            packet,
            inputRefs,
            "agent_platform.engineering_graph.intake",
          ),
        )
      }
      await persistRunEvent(cfg, state, {
        message: "engineering_workflow:intake",
        details: {
          workflow: "engineering_workflow",
          status,
          ready_for_task_decomposition:
            intake.ready_for_task_decomposition === true,
        },
        artifacts,
      })
    }

    if (status === "BLOCKED" || intake.ready_for_task_decomposition !== true) {
      const finalResponse = Array.isArray(intake.required_gates) && intake.required_gates.length > 0
        ? `Engineering gates still block decomposition:\n- ${intake.required_gates
            .map((gate) => String((gate as Record<string, unknown>).rationale ?? "pending gate"))
            .join("\n- ")}`
        : "Engineering intake completed, but task decomposition is still blocked by unresolved gates."
      return {
        dossier_snapshot: dossierSnapshot,
        engineering_session_id: intake.engineering_session_id as string | undefined,
        problem_brief: problemBrief,
        problem_brief_ref: intake.problem_brief_ref as string | undefined,
        engineering_state: engineeringState,
        engineering_state_ref: intake.engineering_state_ref as string | undefined,
        clarification_questions: clarificationQuestions,
        final_response: finalResponse,
        verification_outcome: "BLOCKED",
        current_step: "complete",
      }
    }

    return {
      dossier_snapshot: dossierSnapshot,
      engineering_session_id: intake.engineering_session_id as string | undefined,
      problem_brief: problemBrief,
      problem_brief_ref: intake.problem_brief_ref as string | undefined,
      engineering_state: engineeringState,
      engineering_state_ref: intake.engineering_state_ref as string | undefined,
      task_queue: taskQueue,
      task_packets: taskPackets,
      task_packet: activeTaskPacket,
      active_task_packet_id:
        typeof activeTaskPacketId === "string" ? activeTaskPacketId : undefined,
      clarification_questions: clarificationQuestions,
      current_step: "route_structure",
    }
  }
}

function buildRouteStructure(cfg: PlatformConfig) {
  return async function routeStructure(
    state: EngineeringWorkflowStateType,
  ): Promise<Partial<EngineeringWorkflowStateType>> {
    const objective =
      String(state.task_packet?.objective ?? "") ||
      String((state.problem_brief?.problem_statement as Record<string, unknown> | undefined)?.need ?? "") ||
      latestUserContent(state.messages)
    const rid = state.run_id ?? state.active_task_packet_id ?? randomUUID()
    const route = await classifyViaControlPlane(cfg, objective, rid)
    return {
      structure_route: route,
      current_step: "analyze",
    }
  }
}

function buildExecuteWithCost(llm: LLMManager) {
  return async function executeGenerate(
    state: EngineeringWorkflowStateType,
  ): Promise<Partial<EngineeringWorkflowStateType>> {
    const packet = state.task_packet ?? {}
    const packetConstraints = Array.isArray(packet.constraints)
      ? (packet.constraints as string[])
      : []
    const packetAcceptance = Array.isArray(packet.acceptance_criteria)
      ? (packet.acceptance_criteria as string[])
      : []
    const codeGuidance = packet.code_guidance as Record<string, unknown> | undefined
    const guidanceHints = Array.isArray(codeGuidance?.implementation_hints)
      ? (codeGuidance?.implementation_hints as string[])
      : []
    const toolContextParts: string[] = []
    if (state.required_tool_results && state.required_tool_results.length > 0) {
      toolContextParts.push(
        `Required tool results:\n${JSON.stringify(state.required_tool_results, null, 2)}`,
      )
    }
    for (const [toolName, result] of Object.entries(state.tool_results)) {
      toolContextParts.push(`${toolName}:\n${result}`)
    }

    const systemPrompt = [
      "You are executing a governed engineering task packet.",
      `Objective: ${String(packet.objective ?? latestUserContent(state.messages))}`,
      packet.context_summary ? `Context summary:\n${String(packet.context_summary)}` : "",
      packetConstraints.length > 0 ? `Constraints:\n- ${packetConstraints.join("\n- ")}` : "",
      packetAcceptance.length > 0
        ? `Acceptance criteria:\n- ${packetAcceptance.join("\n- ")}`
        : "",
      guidanceHints.length > 0 ? `Code guidance:\n- ${guidanceHints.join("\n- ")}` : "",
      toolContextParts.length > 0 ? toolContextParts.join("\n\n") : "",
      "Do not rely on full chat history as authoritative context; the task packet and artifact refs govern.",
    ]
      .filter(Boolean)
      .join("\n\n")

    const enhancedMessages: ChatMessage[] = [
      { role: "system", content: systemPrompt },
      ...state.messages,
    ]

    try {
      const result = await llm.chatCompletion(enhancedMessages, {
        temperature: 0.4,
        max_tokens: 1000,
      })
      const content = result.choices[0]?.message?.content ?? "No response generated"
      return {
        final_response: content,
        cost_ledger_entries: [
          ...(state.cost_ledger_entries ?? []),
          {
            component: "engineering_workflow.execute_generate",
            model: "local_worker",
            tokens_in: 0,
            tokens_out: 0,
            duration_ms: 0,
            task_packet_id: state.active_task_packet_id,
          },
        ],
        current_step: "verification",
      }
    } catch (error) {
      const msg =
        error instanceof LLMBackendError
          ? `LLM service error: ${error.message}`
          : `Error generating response: ${error instanceof Error ? error.message : String(error)}`
      return {
        final_response: msg,
        verification_outcome: "FAILED",
        current_step: "complete",
      }
    }
  }
}

function buildVerificationEngineering(cfg: PlatformConfig) {
  return async function verificationEngineering(
    state: EngineeringWorkflowStateType,
  ): Promise<Partial<EngineeringWorkflowStateType>> {
    const wc = state.workflow_config ?? {}
    const forced = wc.force_verification_outcome as string | undefined
    let outcome = "PASS"
    if (forced === "REWORK" || forced === "ESCALATE") {
      outcome = forced
    } else {
      const openIssues = Array.isArray(state.engineering_state?.open_issues)
        ? (state.engineering_state?.open_issues as Array<Record<string, unknown>>)
        : []
      if (openIssues.some((issue) => issue.blocking === true)) {
        outcome = "ESCALATE"
      }
      const objective = String(state.task_packet?.objective ?? "").toLowerCase()
      if (objective.includes("rework verification")) {
        outcome = "REWORK"
      }
    }

    const budget = state.task_packet?.budget_policy as Record<string, unknown> | undefined
    if (budget?.allow_escalation === false && outcome === "ESCALATE") {
      outcome = "REWORK"
    }
    const validatedRefs = Array.isArray(state.task_packet?.input_artifact_refs)
      ? ([...(state.task_packet?.input_artifact_refs as string[])] as string[])
      : []
    if (state.problem_brief_ref) validatedRefs.unshift(state.problem_brief_ref)
    if (state.engineering_state_ref) validatedRefs.unshift(state.engineering_state_ref)
    const dedupedRefs = Array.from(new Set(validatedRefs))
    const packetId = state.task_packet?.task_packet_id
    const sourcePacket =
      typeof packetId === "string" && /^[0-9a-f-]{36}$/i.test(packetId)
        ? packetId
        : randomUUID()
    const report: Record<string, unknown> = {
      verification_report_id: randomUUID(),
      schema_version: "1.0.0",
      outcome,
      reasons: outcome === "PASS" ? [] : ["engineering_gate"],
      blocking_findings:
        outcome === "PASS"
          ? []
          : [
              {
                code: outcome === "ESCALATE" ? "ENGINEERING_GATE_BLOCKED" : "VERIFICATION_REWORK",
                severity: "high",
                artifact_ref: dedupedRefs[0] ?? null,
              },
            ],
      recommended_next_action:
        outcome === "ESCALATE" ? "create_escalation_packet" : "continue",
      validated_artifact_refs: dedupedRefs,
      source_task_packet_id: sourcePacket,
      created_at: new Date().toISOString(),
    }
    await persistRunEvent(cfg, state, {
      message: "engineering_workflow:verification_gate",
      details: {
        verification_outcome: report.outcome,
        workflow: "engineering_workflow",
      },
      artifacts: [
        typedArtifact(
          "VERIFICATION_REPORT",
          report,
          dedupedRefs,
          "agent_platform.engineering_graph.verification",
        ),
      ],
    })
    return {
      verification_outcome: outcome,
      verification_report: report,
      current_step: "typed_escalation",
    }
  }
}

function buildTypedEscalation(
  cfg: PlatformConfig,
  apiBrainCall?: (packet: string) => Promise<string>,
) {
  return async function typedEscalation(
    state: EngineeringWorkflowStateType,
  ): Promise<Partial<EngineeringWorkflowStateType>> {
    if (state.verification_outcome !== "ESCALATE" || !state.verification_report || !state.engineering_state) {
      return { current_step: "synthesize" }
    }

    const built = await postControlPlane(cfg, "/api/control-plane/engineering/build-escalation", {
      engineering_state: state.engineering_state,
      verification_report: state.verification_report,
      problem_brief_ref: state.problem_brief_ref,
      verification_report_ref:
        state.verification_report && typeof state.verification_report.verification_report_id === "string"
          ? `artifact://verification_report/${state.verification_report.verification_report_id}`
          : null,
    })

    if (built.error === true) {
      return {
        final_response: `${state.final_response ?? ""}\n\nTyped escalation failed: ${String(built.body ?? built.reason ?? "unknown error")}`.trim(),
        current_step: "complete",
      }
    }

    const escalationPacket = built.escalation_packet as Record<string, unknown> | undefined
    if (escalationPacket) {
      await persistRunEvent(cfg, state, {
        message: "engineering_workflow:typed_escalation",
        details: {
          workflow: "engineering_workflow",
          escalation_reason: escalationPacket.reason,
        },
        artifacts: [
          typedArtifact(
            "ESCALATION_RECORD",
            escalationPacket,
            Array.isArray(escalationPacket.supporting_artifact_refs)
              ? (escalationPacket.supporting_artifact_refs as string[])
              : [],
            "agent_platform.engineering_graph.typed_escalation",
          ),
        ],
      })
    }

    if (apiBrainCall && state.workflow_config?.allow_api_brain === true && escalationPacket) {
      const packet = JSON.stringify(
        {
          type: "ESCALATION_PACKET",
          escalation_packet: escalationPacket,
        },
        null,
        2,
      )
      const output = await apiBrainCall(packet)
      return {
        escalation_packet: escalationPacket,
        api_brain_packet: packet,
        api_brain_output: output,
        escalation_count: state.escalation_count + 1,
        current_step: "synthesize",
      }
    }

    return {
      escalation_packet: escalationPacket,
      current_step: "synthesize",
    }
  }
}

function synthesizeEngineering(
  state: EngineeringWorkflowStateType,
): Partial<EngineeringWorkflowStateType> {
  if (state.current_step === "complete") {
    return {}
  }
  const parts: string[] = []
  if (state.final_response) {
    parts.push(state.final_response)
  }
  if (state.verification_outcome) {
    parts.push(`[verification:${state.verification_outcome}]`)
  }
  if (state.escalation_packet) {
    parts.push(
      `[typed_escalation:${String(state.escalation_packet.reason ?? "requested")}]`,
    )
  }
  if (state.api_brain_output) {
    parts.push(`Strategic review:\n${state.api_brain_output}`)
  }
  return {
    final_response: parts.join("\n\n").trim(),
    current_step: "complete",
  }
}

export function createEngineeringWorkflow(
  cfg: PlatformConfig,
  llm: LLMManager,
  apiBrainCall?: (packet: string) => Promise<string>,
) {
  const engineeringIntake = buildEngineeringIntake(cfg)
  const routeStructure = buildRouteStructure(cfg)
  const gatherContext = buildGatherContext(cfg)
  const executeGenerate = buildExecuteWithCost(llm)
  const verification = buildVerificationEngineering(cfg)
  const typedEscalation = buildTypedEscalation(cfg, apiBrainCall)

  const graph = new StateGraph(EngineeringWorkflowAnnotation)
    .addNode("intake", intakeEngineering as any)
    .addNode("engineering_intake", engineeringIntake)
    .addNode("route_structure", routeStructure)
    .addNode("analyze", analyzeRequest as any)
    .addNode("gather_context", gatherContext as any)
    .addNode("execute_generate", executeGenerate as any)
    .addNode("verification", verification as any)
    .addNode("typed_escalation", typedEscalation as any)
    .addNode("synthesize", synthesizeEngineering as any)
    .addEdge(START, "intake")
    .addEdge("intake", "engineering_intake")
    .addConditionalEdges("engineering_intake", (state) =>
      state.current_step === "complete" ? END : "route_structure",
    )
    .addEdge("route_structure", "analyze")
    .addConditionalEdges("analyze", (state) =>
      state.tools_needed.length > 0 ? "gather_context" : "execute_generate",
    )
    .addEdge("gather_context", "execute_generate")
    .addEdge("execute_generate", "verification")
    .addEdge("verification", "typed_escalation")
    .addEdge("typed_escalation", "synthesize")
    .addEdge("synthesize", END)

  return graph.compile()
}
