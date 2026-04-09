/**
 * Engineering-governed LangGraph workflow.
 *
 * Strict engineering runs are packet-driven: `problem_brief -> engineering_state ->
 * task_queue -> task_packet`. Chat is the operator surface only; execution and
 * verification follow the active task packet and its selected executor.
 */

import { randomUUID } from "node:crypto"
import { Annotation, END, START, StateGraph } from "@langchain/langgraph"
import type { PlatformConfig } from "../config.js"
import { LLMBackendError, LLMManager } from "../llm/manager.js"
import {
  postInferCoding,
  postInferMultimodal,
} from "../llm/model-runtime-client.js"
import type { ChatMessage } from "../tools/wrkhrs.js"

export const EngineeringWorkflowAnnotation = Annotation.Root({
  messages: Annotation<ChatMessage[]>(),
  current_step: Annotation<string>(),
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
  engagement_mode: Annotation<string | undefined>(),
  engagement_mode_source: Annotation<string | undefined>(),
  engagement_mode_confidence: Annotation<number | undefined>(),
  engagement_mode_reasons: Annotation<string[]>({
    reducer: (_left, right) => right,
    default: () => [],
  }),
  minimum_engagement_mode: Annotation<string | undefined>(),
  pending_mode_change: Annotation<Record<string, unknown> | undefined>(),
  lifecycle_reason: Annotation<string | undefined>(),
  lifecycle_detail: Annotation<Record<string, unknown> | undefined>(),
  task_plan: Annotation<Record<string, unknown> | undefined>(),
  project_context: Annotation<Record<string, unknown> | undefined>(),
  engineering_session_id: Annotation<string | undefined>(),
  active_task_packet_id: Annotation<string | undefined>(),
  active_task_packet_ref: Annotation<string | undefined>(),
  active_selected_executor: Annotation<string | undefined>(),
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
  required_gates: Annotation<Record<string, unknown>[]>({
    reducer: (_left, right) => right,
    default: () => [],
  }),
  ready_for_task_decomposition: Annotation<boolean | undefined>(),
  verification_outcome: Annotation<string | undefined>(),
  verification_report: Annotation<Record<string, unknown> | undefined>(),
  escalation_packet: Annotation<Record<string, unknown> | undefined>(),
  generated_artifacts: Annotation<Record<string, unknown>[]>({
    reducer: (left, right) => [...left, ...right],
    default: () => [],
  }),
  generated_artifact_refs: Annotation<string[]>({
    reducer: (left, right) => [...left, ...right],
    default: () => [],
  }),
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
  producerExecutor: string,
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
      executor: producerExecutor,
    },
    input_artifact_refs: inputRefs,
    supersedes: [],
    payload,
  }
}

function artifactRefFromEnvelope(artifact: Record<string, unknown>): string | undefined {
  const artifactType = String(artifact.artifact_type ?? "").trim().toLowerCase()
  const artifactId = String(artifact.artifact_id ?? "").trim()
  if (!artifactType || !artifactId) {
    return undefined
  }
  return `artifact://${artifactType}/${artifactId}`
}

function packetInputRefs(packet: Record<string, unknown> | undefined): string[] {
  if (!packet) return []
  return Array.isArray(packet.input_artifact_refs)
    ? (packet.input_artifact_refs as string[]).filter(Boolean)
    : []
}

function packetOutputArtifactType(packet: Record<string, unknown> | undefined): string {
  if (!packet || !Array.isArray(packet.required_outputs) || packet.required_outputs.length === 0) {
    return "DECISION_LOG"
  }
  const first = packet.required_outputs[0] as Record<string, unknown> | undefined
  return String(first?.artifact_type ?? "DECISION_LOG")
}

function packetExecutor(packet: Record<string, unknown> | undefined): string | undefined {
  const routing = packet?.routing_metadata as Record<string, unknown> | undefined
  const selected = String(routing?.selected_executor ?? "").trim()
  return selected || undefined
}

function packetPrompt(
  packet: Record<string, unknown>,
  state: EngineeringWorkflowStateType,
): string {
  const constraints = Array.isArray(packet.constraints) ? (packet.constraints as string[]) : []
  const acceptance = Array.isArray(packet.acceptance_criteria)
    ? (packet.acceptance_criteria as string[])
    : []
  const guidance = (packet.code_guidance as Record<string, unknown> | undefined) ?? {}
  const implementationHints = Array.isArray(guidance.implementation_hints)
    ? (guidance.implementation_hints as string[])
    : []
  const toolResults = state.required_tool_results && state.required_tool_results.length > 0
    ? `Required tool results:\n${JSON.stringify(state.required_tool_results, null, 2)}`
    : ""
  return [
    `Objective: ${String(packet.objective ?? latestUserContent(state.messages))}`,
    packet.context_summary ? `Context summary:\n${String(packet.context_summary)}` : "",
    constraints.length > 0 ? `Constraints:\n- ${constraints.join("\n- ")}` : "",
    acceptance.length > 0 ? `Acceptance criteria:\n- ${acceptance.join("\n- ")}` : "",
    implementationHints.length > 0
      ? `Implementation hints:\n- ${implementationHints.join("\n- ")}`
      : "",
    toolResults,
    "Use only the task packet and artifact refs as governing context.",
  ]
    .filter(Boolean)
    .join("\n\n")
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
      task_id: state.task_id,
      run_id: state.run_id,
      task_packet: state.task_packet,
      task_plan: state.task_plan,
      project_context: state.project_context,
      engagement_mode:
        state.engagement_mode ?? String(state.workflow_config?.engagement_mode ?? ""),
      engagement_mode_source:
        state.engagement_mode_source ??
        String(state.workflow_config?.engagement_mode_source ?? ""),
      engagement_mode_confidence:
        state.engagement_mode_confidence ??
        (typeof state.workflow_config?.engagement_mode_confidence === "number"
          ? state.workflow_config.engagement_mode_confidence
          : undefined),
      engagement_mode_reasons:
        state.engagement_mode_reasons.length > 0
          ? state.engagement_mode_reasons
          : Array.isArray(state.workflow_config?.engagement_mode_reasons)
            ? (state.workflow_config.engagement_mode_reasons as string[])
            : [],
      minimum_engagement_mode:
        state.minimum_engagement_mode ??
        String(state.workflow_config?.minimum_engagement_mode ?? ""),
      pending_mode_change:
        state.pending_mode_change ??
        ((state.workflow_config?.pending_mode_change as Record<string, unknown> | undefined) ??
          undefined),
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
    const activeTaskPacketRef =
      typeof activeTaskPacketId === "string"
        ? `artifact://task_packet/${activeTaskPacketId}`
        : undefined
    const selectedExecutor = packetExecutor(activeTaskPacket)
    const status = String(intake.status ?? "")
    const problemBrief = intake.problem_brief as Record<string, unknown> | undefined
    const engineeringState = intake.engineering_state as Record<string, unknown> | undefined
    const taskQueue = intake.task_queue as Record<string, unknown> | undefined
    const requiredGates = Array.isArray(intake.required_gates)
      ? (intake.required_gates as Record<string, unknown>[])
      : []
    const engagementMode =
      typeof intake.engagement_mode === "string" ? intake.engagement_mode : state.engagement_mode
    const engagementModeSource =
      typeof intake.engagement_mode_source === "string"
        ? intake.engagement_mode_source
        : state.engagement_mode_source
    const engagementModeConfidence =
      typeof intake.engagement_mode_confidence === "number"
        ? intake.engagement_mode_confidence
        : state.engagement_mode_confidence
    const engagementModeReasons = Array.isArray(intake.engagement_mode_reasons)
      ? (intake.engagement_mode_reasons as string[])
      : state.engagement_mode_reasons
    const minimumEngagementMode =
      typeof intake.minimum_engagement_mode === "string"
        ? intake.minimum_engagement_mode
        : state.minimum_engagement_mode
    const pendingModeChange =
      intake.pending_mode_change && typeof intake.pending_mode_change === "object"
        ? (intake.pending_mode_change as Record<string, unknown>)
        : state.pending_mode_change

    const artifacts: Array<Record<string, unknown>> = []
    if (problemBrief) {
      artifacts.push(
        typedArtifact(
          "PROBLEM_BRIEF",
          problemBrief,
          [],
          "agent_platform.engineering_graph.intake",
          "local_general_model",
        ),
      )
    }
    if (engineeringState) {
      artifacts.push(
        typedArtifact(
          "ENGINEERING_STATE",
          engineeringState,
          [String(intake.problem_brief_ref ?? "")].filter(Boolean),
          "agent_platform.engineering_graph.intake",
          "local_general_model",
        ),
      )
    }
    if (taskQueue) {
      artifacts.push(
        typedArtifact(
          "TASK_QUEUE",
          taskQueue,
          [String(intake.problem_brief_ref ?? ""), String(intake.engineering_state_ref ?? "")].filter(
            Boolean,
          ),
          "agent_platform.engineering_graph.intake",
          "local_general_model",
        ),
      )
    }
    for (const packet of taskPackets) {
      artifacts.push(
        typedArtifact(
          "TASK_PACKET",
          packet,
          packetInputRefs(packet),
          "agent_platform.engineering_graph.intake",
          "local_general_model",
        ),
      )
    }
    if (artifacts.length > 0) {
      await persistRunEvent(cfg, state, {
        message: "engineering_workflow:intake",
        details: {
          workflow: "engineering_workflow",
          status,
          ready_for_task_decomposition: intake.ready_for_task_decomposition === true,
        },
        artifacts,
      })
    }

    if (status === "CLARIFICATION_REQUIRED") {
      return {
        dossier_snapshot: dossierSnapshot,
        engineering_session_id: intake.engineering_session_id as string | undefined,
        engagement_mode: engagementMode,
        engagement_mode_source: engagementModeSource,
        engagement_mode_confidence: engagementModeConfidence,
        engagement_mode_reasons: engagementModeReasons,
        minimum_engagement_mode: minimumEngagementMode,
        pending_mode_change: pendingModeChange,
        lifecycle_reason: "clarification_required",
        lifecycle_detail: { clarification_questions: clarificationQuestions.length },
        problem_brief: problemBrief,
        problem_brief_ref: intake.problem_brief_ref as string | undefined,
        clarification_questions: clarificationQuestions,
        required_gates: requiredGates,
        ready_for_task_decomposition: false,
        final_response:
          `Engineering clarification required:\n- ${clarificationQuestions.join("\n- ")}`,
        verification_outcome: "CLARIFICATION_REQUIRED",
        current_step: "complete",
      }
    }

    if (status === "BLOCKED" || intake.ready_for_task_decomposition !== true) {
      const finalResponse =
        requiredGates.length > 0
          ? `Engineering gates still block decomposition:\n- ${requiredGates
              .map((gate) => String(gate.rationale ?? "pending gate"))
              .join("\n- ")}`
          : "Engineering intake completed, but task decomposition is still blocked by unresolved gates."
      return {
        dossier_snapshot: dossierSnapshot,
        engineering_session_id: intake.engineering_session_id as string | undefined,
        engagement_mode: engagementMode,
        engagement_mode_source: engagementModeSource,
        engagement_mode_confidence: engagementModeConfidence,
        engagement_mode_reasons: engagementModeReasons,
        minimum_engagement_mode: minimumEngagementMode,
        pending_mode_change: pendingModeChange,
        lifecycle_reason: "governance_gate",
        lifecycle_detail: { required_gates: requiredGates.length },
        problem_brief: problemBrief,
        problem_brief_ref: intake.problem_brief_ref as string | undefined,
        engineering_state: engineeringState,
        engineering_state_ref: intake.engineering_state_ref as string | undefined,
        task_queue: taskQueue,
        task_packets: taskPackets,
        required_gates: requiredGates,
        clarification_questions: clarificationQuestions,
        ready_for_task_decomposition: false,
        final_response: finalResponse,
        verification_outcome: "BLOCKED",
        current_step: "complete",
      }
    }

    if (!activeTaskPacket || !selectedExecutor) {
      return {
        dossier_snapshot: dossierSnapshot,
        engineering_session_id: intake.engineering_session_id as string | undefined,
        engagement_mode: engagementMode,
        engagement_mode_source: engagementModeSource,
        engagement_mode_confidence: engagementModeConfidence,
        engagement_mode_reasons: engagementModeReasons,
        minimum_engagement_mode: minimumEngagementMode,
        pending_mode_change: pendingModeChange,
        lifecycle_reason: "executor_unavailable",
        lifecycle_detail: { reason: "active_task_packet_missing" },
        problem_brief: problemBrief,
        problem_brief_ref: intake.problem_brief_ref as string | undefined,
        engineering_state: engineeringState,
        engineering_state_ref: intake.engineering_state_ref as string | undefined,
        task_queue: taskQueue,
        task_packets: taskPackets,
        required_gates: requiredGates,
        ready_for_task_decomposition: true,
        final_response:
          "Strict engineering intake succeeded, but no active governed task packet is available for execution.",
        verification_outcome: "FAILED",
        current_step: "complete",
      }
    }

    return {
      dossier_snapshot: dossierSnapshot,
      engineering_session_id: intake.engineering_session_id as string | undefined,
      engagement_mode: engagementMode,
      engagement_mode_source: engagementModeSource,
      engagement_mode_confidence: engagementModeConfidence,
      engagement_mode_reasons: engagementModeReasons,
      minimum_engagement_mode: minimumEngagementMode,
      pending_mode_change: pendingModeChange,
      problem_brief: problemBrief,
      problem_brief_ref: intake.problem_brief_ref as string | undefined,
      engineering_state: engineeringState,
      engineering_state_ref: intake.engineering_state_ref as string | undefined,
      task_queue: taskQueue,
      task_packets: taskPackets,
      task_packet: activeTaskPacket,
      active_task_packet_id: typeof activeTaskPacketId === "string" ? activeTaskPacketId : undefined,
      active_task_packet_ref: activeTaskPacketRef,
      active_selected_executor: selectedExecutor,
      clarification_questions: clarificationQuestions,
      required_gates: requiredGates,
      ready_for_task_decomposition: true,
      current_step: "execute_packet",
    }
  }
}

function buildExecuteTaskPacket(cfg: PlatformConfig, llm: LLMManager) {
  return async function executeTaskPacket(
    state: EngineeringWorkflowStateType,
  ): Promise<Partial<EngineeringWorkflowStateType>> {
    const packet = state.task_packet
    if (!packet) {
      return {
        final_response: "Strict engineering execution failed: missing active task packet.",
        verification_outcome: "BLOCKED",
        lifecycle_reason: "governance_gate",
        lifecycle_detail: { reason: "active_task_packet_missing" },
        current_step: "complete",
      }
    }
    const selectedExecutor = packetExecutor(packet)
    if (!selectedExecutor) {
      return {
        final_response: "Strict engineering execution failed: task packet missing selected executor.",
        verification_outcome: "BLOCKED",
        lifecycle_reason: "executor_unavailable",
        lifecycle_detail: { reason: "selected_executor_missing" },
        current_step: "complete",
      }
    }

    const inputRefs = packetInputRefs(packet)
    const artifactType = packetOutputArtifactType(packet)
    const prompt = packetPrompt(packet, state)

    try {
      if (selectedExecutor === "coding_model") {
        if (!cfg.modelRuntimeBaseUrl) {
          return {
            final_response:
              "Strict engineering execution blocked: coding_model requires MODEL_RUNTIME_URL.",
            verification_outcome: "BLOCKED",
            lifecycle_reason: "executor_unavailable",
            lifecycle_detail: { executor: selectedExecutor, dependency: "MODEL_RUNTIME_URL" },
            current_step: "complete",
          }
        }
        const response = await postInferCoding(cfg, packet)
        const payload = {
          schema_version: "1.0.0",
          generated_from_task_packet_id: packet.task_packet_id,
          selected_executor: selectedExecutor,
          text: response.text ?? "",
          model_id_resolved: response.model_id_resolved,
          usage: response.usage,
          created_at: new Date().toISOString(),
        }
        const artifact = typedArtifact(
          artifactType,
          payload,
          inputRefs,
          "agent_platform.engineering_graph.execute.coding",
          selectedExecutor,
        )
        await persistRunEvent(cfg, state, {
          message: "engineering_workflow:execute_packet",
          details: {
            selected_executor: selectedExecutor,
            active_task_packet_ref: state.active_task_packet_ref,
          },
          artifacts: [artifact],
        })
        return {
          final_response: response.text ?? "",
          generated_artifacts: [artifact],
          generated_artifact_refs: [artifactRefFromEnvelope(artifact)].filter(
            Boolean,
          ) as string[],
          cost_ledger_entries: [
            {
              component: "engineering_workflow.execute_packet",
              model: response.model_id_resolved,
              tokens_in: response.usage.prompt_tokens,
              tokens_out: response.usage.completion_tokens,
              duration_ms: response.usage.latency_ms,
              task_packet_id: state.active_task_packet_id,
            },
          ],
          current_step: "verification",
        }
      }

      if (selectedExecutor === "multimodal_model") {
        if (!cfg.modelRuntimeBaseUrl) {
          return {
            final_response:
              "Strict engineering execution blocked: multimodal_model requires MODEL_RUNTIME_URL.",
            verification_outcome: "BLOCKED",
            lifecycle_reason: "executor_unavailable",
            lifecycle_detail: { executor: selectedExecutor, dependency: "MODEL_RUNTIME_URL" },
            current_step: "complete",
          }
        }
        const response = await postInferMultimodal(cfg, packet)
        const payload = {
          schema_version: "1.0.0",
          generated_from_task_packet_id: packet.task_packet_id,
          selected_executor: selectedExecutor,
          text: response.text ?? "",
          structured_output: response.structured_output ?? {},
          model_id_resolved: response.model_id_resolved,
          usage: response.usage,
          created_at: new Date().toISOString(),
        }
        const artifact = typedArtifact(
          artifactType,
          payload,
          inputRefs,
          "agent_platform.engineering_graph.execute.multimodal",
          selectedExecutor,
        )
        await persistRunEvent(cfg, state, {
          message: "engineering_workflow:execute_packet",
          details: {
            selected_executor: selectedExecutor,
            active_task_packet_ref: state.active_task_packet_ref,
          },
          artifacts: [artifact],
        })
        return {
          final_response: response.text ?? "Structured multimodal extraction complete.",
          generated_artifacts: [artifact],
          generated_artifact_refs: [artifactRefFromEnvelope(artifact)].filter(
            Boolean,
          ) as string[],
          cost_ledger_entries: [
            {
              component: "engineering_workflow.execute_packet",
              model: response.model_id_resolved,
              tokens_in: response.usage.prompt_tokens,
              tokens_out: response.usage.completion_tokens,
              duration_ms: response.usage.latency_ms,
              task_packet_id: state.active_task_packet_id,
            },
          ],
          current_step: "verification",
        }
      }

      if (selectedExecutor === "local_general_model") {
        const result = await llm.chatCompletion(
          [
            {
              role: "system",
              content:
                "You are the local general-model executor for a governed engineering packet. " +
                "Summarize or synthesize only; do not mutate repositories or invent missing evidence.",
            },
            { role: "user", content: prompt },
          ],
          { temperature: 0.2, max_tokens: 900 },
        )
        const content = result.choices[0]?.message?.content ?? "No response generated"
        const payload = {
          schema_version: "1.0.0",
          generated_from_task_packet_id: packet.task_packet_id,
          selected_executor: selectedExecutor,
          text: content,
          created_at: new Date().toISOString(),
        }
        const artifact = typedArtifact(
          artifactType,
          payload,
          inputRefs,
          "agent_platform.engineering_graph.execute.local_general",
          selectedExecutor,
        )
        await persistRunEvent(cfg, state, {
          message: "engineering_workflow:execute_packet",
          details: {
            selected_executor: selectedExecutor,
            active_task_packet_ref: state.active_task_packet_ref,
          },
          artifacts: [artifact],
        })
        return {
          final_response: content,
          generated_artifacts: [artifact],
          generated_artifact_refs: [artifactRefFromEnvelope(artifact)].filter(
            Boolean,
          ) as string[],
          cost_ledger_entries: [
            {
              component: "engineering_workflow.execute_packet",
              model: "local_general_model",
              tokens_in: 0,
              tokens_out: 0,
              duration_ms: 0,
              task_packet_id: state.active_task_packet_id,
            },
          ],
          current_step: "verification",
        }
      }

      if (selectedExecutor === "deterministic_validator") {
        return {
          final_response:
            "Deterministic validator selected as the active executor; proceeding directly to verification.",
          current_step: "verification",
        }
      }

      if (selectedExecutor === "strategic_reviewer") {
        if (!state.escalation_packet) {
          return {
            final_response:
              "Strict engineering execution blocked: strategic_reviewer may only run after typed escalation.",
            verification_outcome: "BLOCKED",
            lifecycle_reason: "awaiting_strategic_review",
            lifecycle_detail: { executor: selectedExecutor, escalation_packet_present: false },
            current_step: "complete",
          }
        }
        const packetText = JSON.stringify(state.escalation_packet, null, 2)
        const result = await llm.chatCompletion(
          [
            {
              role: "system",
              content:
                "You are the strategic reviewer for a typed engineering escalation packet. " +
                "Return compact decision guidance only.",
            },
            { role: "user", content: packetText },
          ],
          { temperature: 0.2, max_tokens: 700 },
        )
        const content = result.choices[0]?.message?.content ?? "No response generated"
        return {
          final_response: content,
          current_step: "verification",
        }
      }

      return {
        final_response: `Strict engineering execution blocked: unsupported executor '${selectedExecutor}'.`,
        verification_outcome: "BLOCKED",
        lifecycle_reason: "executor_unavailable",
        lifecycle_detail: { executor: selectedExecutor },
        current_step: "complete",
      }
    } catch (error) {
      const msg =
        error instanceof LLMBackendError
          ? `LLM service error: ${error.message}`
          : `Engineering packet execution failed: ${
              error instanceof Error ? error.message : String(error)
            }`
      return {
        final_response: msg,
        verification_outcome: "BLOCKED",
        lifecycle_reason: "executor_unavailable",
        lifecycle_detail: {
          executor: selectedExecutor,
          error: error instanceof Error ? error.message : String(error),
        },
        current_step: "complete",
      }
    }
  }
}

function buildVerificationEngineering(cfg: PlatformConfig) {
  return async function verificationEngineering(
    state: EngineeringWorkflowStateType,
  ): Promise<Partial<EngineeringWorkflowStateType>> {
    const validationPacket =
      state.task_packets.find((packet) => packet.task_type === "VALIDATION") ?? undefined
    const sourcePacket = validationPacket ?? state.task_packet
    const sourcePacketId =
      typeof sourcePacket?.task_packet_id === "string" &&
      /^[0-9a-f-]{36}$/i.test(sourcePacket.task_packet_id)
        ? sourcePacket.task_packet_id
        : randomUUID()
    const generatedArtifacts = state.generated_artifacts ?? []
    const generatedArtifactRefs = (state.generated_artifact_refs ?? []).filter(Boolean)
    const validatedRefs = Array.from(
      new Set(
        [
          ...packetInputRefs(sourcePacket),
          ...generatedArtifactRefs,
          state.problem_brief_ref,
          state.engineering_state_ref,
        ].filter(Boolean) as string[],
      ),
    )
    const gateResults: Array<Record<string, unknown>> = []
    const blockingFindings: Array<Record<string, unknown>> = []

    if (!validationPacket) {
      gateResults.push({
        gate_id: "validator_packet_present",
        gate_kind: "policy",
        status: "FAIL",
        detail: "Strict engineering task queue did not provide a deterministic validation packet.",
      })
      blockingFindings.push({
        code: "VALIDATION_PACKET_MISSING",
        severity: "high",
        artifact_ref: state.active_task_packet_ref ?? null,
      })
    } else if (packetExecutor(validationPacket) !== "deterministic_validator") {
      gateResults.push({
        gate_id: "validator_executor",
        gate_kind: "policy",
        status: "FAIL",
        detail: "Validation packet must select deterministic_validator.",
      })
      blockingFindings.push({
        code: "VALIDATOR_EXECUTOR_MISMATCH",
        severity: "high",
        artifact_ref: `artifact://task_packet/${String(validationPacket.task_packet_id ?? "")}`,
      })
    } else {
      gateResults.push({
        gate_id: "validator_packet_present",
        gate_kind: "policy",
        status: "PASS",
        detail: "Deterministic validation packet is present and correctly routed.",
      })
    }

    const requiredOutputs = Array.isArray(state.task_packet?.required_outputs)
      ? (state.task_packet?.required_outputs as Array<Record<string, unknown>>)
      : []
    for (let index = 0; index < requiredOutputs.length; index += 1) {
      const output = requiredOutputs[index] ?? {}
      const expectedArtifactType = String(output.artifact_type ?? "").trim()
      const hasArtifact = generatedArtifacts.some(
        (artifact) => String(artifact.artifact_type ?? "") === expectedArtifactType,
      )
      gateResults.push({
        gate_id: `required_output_${index + 1}`,
        gate_kind: "schema",
        status: hasArtifact ? "PASS" : "FAIL",
        detail: hasArtifact
          ? `Generated required artifact ${expectedArtifactType}.`
          : `Missing required artifact ${expectedArtifactType}.`,
      })
      if (!hasArtifact) {
        blockingFindings.push({
          code: "REQUIRED_OUTPUT_MISSING",
          severity: "high",
          artifact_ref: state.active_task_packet_ref ?? null,
        })
      }
    }

    const validationRequirements = Array.isArray(validationPacket?.validation_requirements)
      ? (validationPacket?.validation_requirements as string[])
      : []
    gateResults.push({
      gate_id: "validation_requirements",
      gate_kind: "tests",
      status: validationRequirements.length > 0 ? "PASS" : "FAIL",
      detail:
        validationRequirements.length > 0
          ? "Deterministic validation requirements are present."
          : "Validation requirements are missing.",
    })
    if (validationRequirements.length === 0) {
      blockingFindings.push({
        code: "VALIDATION_REQUIREMENTS_MISSING",
        severity: "high",
        artifact_ref: state.active_task_packet_ref ?? null,
      })
    }

    for (const gate of state.required_gates ?? []) {
      const pending = String(gate.status ?? "PENDING") !== "SATISFIED"
      gateResults.push({
        gate_id: String(gate.gate_id ?? "required_gate"),
        gate_kind: "policy",
        status: pending ? "FAIL" : "PASS",
        detail: String(gate.rationale ?? "Required engineering gate"),
      })
      if (pending) {
        blockingFindings.push({
          code: "ENGINEERING_GATE_PENDING",
          severity: "high",
          artifact_ref: state.problem_brief_ref ?? null,
        })
      }
    }

    const openIssues = Array.isArray(state.engineering_state?.open_issues)
      ? (state.engineering_state?.open_issues as Array<Record<string, unknown>>)
      : []
    const blockingIssues = openIssues.filter((issue) => issue.blocking === true)
    for (const issue of blockingIssues) {
      gateResults.push({
        gate_id: `open_issue_${String(issue.issue_id ?? randomUUID())}`,
        gate_kind: "policy",
        status: "FAIL",
        detail: String(issue.description ?? "Blocking engineering issue"),
      })
      blockingFindings.push({
        code: "BLOCKING_ENGINEERING_ISSUE",
        severity: "high",
        artifact_ref:
          Array.isArray(issue.source_artifact_refs) && issue.source_artifact_refs.length > 0
            ? String(issue.source_artifact_refs[0])
            : state.problem_brief_ref ?? null,
      })
    }

    const conflicts = Array.isArray(state.engineering_state?.conflicts)
      ? (state.engineering_state?.conflicts as Array<Record<string, unknown>>)
      : []
    const openConflicts = conflicts.filter(
      (conflict) => String(conflict.resolution_status ?? "open") === "open",
    )
    for (const conflict of openConflicts) {
      gateResults.push({
        gate_id: `conflict_${String(conflict.conflict_id ?? randomUUID())}`,
        gate_kind: "policy",
        status: "FAIL",
        detail: String(conflict.description ?? "Open engineering conflict"),
      })
      blockingFindings.push({
        code: "OPEN_ENGINEERING_CONFLICT",
        severity: "high",
        artifact_ref:
          Array.isArray(conflict.involved_artifact_refs) && conflict.involved_artifact_refs.length > 0
            ? String(conflict.involved_artifact_refs[0])
            : state.engineering_state_ref ?? null,
      })
    }

    const outcome =
      openConflicts.length > 0 || blockingIssues.length > 0
        ? "ESCALATE"
        : gateResults.some((gate) => gate.status === "FAIL" || gate.status === "ERROR")
          ? "REWORK"
          : "PASS"
    const report: Record<string, unknown> = {
      verification_report_id: randomUUID(),
      schema_version: "1.0.0",
      outcome,
      reasons:
        outcome === "PASS"
          ? []
          : gateResults
              .filter((gate) => gate.status === "FAIL" || gate.status === "ERROR")
              .map((gate) => String(gate.gate_id)),
      blocking_findings: outcome === "PASS" ? [] : blockingFindings,
      gate_results: gateResults,
      recommended_next_action:
        outcome === "ESCALATE"
          ? "create_escalation_packet"
          : outcome === "REWORK"
            ? "revise_task_packet"
            : "continue",
      validated_artifact_refs: validatedRefs.length > 0 ? validatedRefs : ["artifact://verification/none"],
      source_task_packet_id: sourcePacketId,
      created_at: new Date().toISOString(),
    }
    const verificationArtifact = typedArtifact(
      "VERIFICATION_REPORT",
      report,
      report.validated_artifact_refs as string[],
      "agent_platform.engineering_graph.verification",
      "deterministic_validator",
    )
    await persistRunEvent(cfg, state, {
      message: "engineering_workflow:verification_gate",
      details: {
        verification_outcome: report.outcome,
        workflow: "engineering_workflow",
      },
      artifacts: [verificationArtifact],
    })
    return {
      verification_outcome: outcome,
      verification_report: report,
      lifecycle_reason:
        outcome === "ESCALATE"
          ? "awaiting_strategic_review"
          : outcome === "REWORK"
            ? "verification_rework_required"
            : undefined,
      lifecycle_detail:
        outcome === "PASS"
          ? {}
          : {
              blocking_findings: blockingFindings.length,
              failing_gates: gateResults.filter(
                (gate) => gate.status === "FAIL" || gate.status === "ERROR",
              ).length,
            },
      generated_artifacts: [verificationArtifact],
      generated_artifact_refs: [artifactRefFromEnvelope(verificationArtifact)].filter(
        Boolean,
      ) as string[],
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
    if (
      state.verification_outcome !== "ESCALATE" ||
      !state.verification_report ||
      !state.engineering_state
    ) {
      return { current_step: "synthesize" }
    }

    const built = await postControlPlane(cfg, "/api/control-plane/engineering/build-escalation", {
      engineering_state: state.engineering_state,
      verification_report: state.verification_report,
      problem_brief_ref: state.problem_brief_ref,
      verification_report_ref:
        state.verification_report &&
        typeof state.verification_report.verification_report_id === "string"
          ? `artifact://verification_report/${state.verification_report.verification_report_id}`
          : null,
    })

    if (built.error === true) {
      return {
        final_response: `${state.final_response ?? ""}\n\nTyped escalation failed: ${String(
          built.body ?? built.reason ?? "unknown error",
        )}`.trim(),
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
            "strategic_reviewer",
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
        lifecycle_reason: "awaiting_strategic_review",
        lifecycle_detail: { escalation_reason: escalationPacket.reason },
        current_step: "synthesize",
      }
    }

    return {
      escalation_packet: escalationPacket,
      lifecycle_reason: "awaiting_strategic_review",
      lifecycle_detail: { escalation_reason: escalationPacket?.reason },
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
  const executeTaskPacket = buildExecuteTaskPacket(cfg, llm)
  const verification = buildVerificationEngineering(cfg)
  const typedEscalation = buildTypedEscalation(cfg, apiBrainCall)

  const graph = new StateGraph(EngineeringWorkflowAnnotation)
    .addNode("intake", intakeEngineering as any)
    .addNode("engineering_intake", engineeringIntake)
    .addNode("execute_packet", executeTaskPacket as any)
    .addNode("verification", verification as any)
    .addNode("typed_escalation", typedEscalation as any)
    .addNode("synthesize", synthesizeEngineering as any)
    .addEdge(START, "intake")
    .addEdge("intake", "engineering_intake")
    .addConditionalEdges("engineering_intake", (state) =>
      state.current_step === "complete" ? END : "execute_packet",
    )
    .addConditionalEdges("execute_packet", (state) =>
      state.current_step === "complete" ? END : "verification",
    )
    .addConditionalEdges("verification", (state) =>
      state.current_step === "complete" ? END : "typed_escalation",
    )
    .addEdge("typed_escalation", "synthesize")
    .addEdge("synthesize", END)

  return graph.compile()
}
