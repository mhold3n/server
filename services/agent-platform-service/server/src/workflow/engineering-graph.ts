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
import { LLMBackendError } from "../llm/manager.js"
import { OrchestrationEngine } from "../orchestration/engine.js"
import { resolveWorkflowModelRouting } from "../orchestration/runtime-router.js"
import type { ChatMessage } from "../tools/wrkhrs.js"

/** The unified memory schema for the Engineering Graph. */
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
  response_mode: Annotation<string | undefined>(),
  response_control_ref: Annotation<string | undefined>(),
  selected_knowledge_pool_refs: Annotation<string[]>({
    reducer: (_left, right) => right,
    default: () => [],
  }),
  selected_module_refs: Annotation<string[]>({
    reducer: (_left, right) => right,
    default: () => [],
  }),
  selected_technique_refs: Annotation<string[]>({
    reducer: (_left, right) => right,
    default: () => [],
  }),
  selected_theory_refs: Annotation<string[]>({
    reducer: (_left, right) => right,
    default: () => [],
  }),
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
  knowledge_pool_assessment: Annotation<Record<string, unknown> | undefined>(),
  knowledge_pool_assessment_ref: Annotation<string | undefined>(),
  knowledge_pool_coverage: Annotation<string | undefined>(),
  knowledge_candidate_refs: Annotation<string[]>({
    reducer: (_left, right) => right,
    default: () => [],
  }),
  knowledge_role_contexts: Annotation<Record<string, Record<string, unknown>> | undefined>(),
  knowledge_role_context_refs: Annotation<string[]>({
    reducer: (_left, right) => right,
    default: () => [],
  }),
  knowledge_gaps: Annotation<string[]>({
    reducer: (_left, right) => right,
    default: () => [],
  }),
  knowledge_required: Annotation<boolean | undefined>(),
  wiki_overlay_context: Annotation<string | undefined>(),
  wiki_edit_proposals: Annotation<Record<string, unknown>[]>({
    reducer: (_left, right) => right,
    default: () => [],
  }),
  wiki_edit_proposal_refs: Annotation<string[]>({
    reducer: (_left, right) => right,
    default: () => [],
  }),
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
      : typeof payload.knowledge_pool_assessment_id === "string"
        ? payload.knowledge_pool_assessment_id
      : typeof payload.engineering_state_id === "string"
        ? payload.engineering_state_id
        : typeof payload.role_context_bundle_id === "string"
          ? payload.role_context_bundle_id
        : typeof payload.task_queue_id === "string"
          ? payload.task_queue_id
          : typeof payload.task_packet_id === "string"
            ? payload.task_packet_id
            : typeof payload.verification_report_id === "string"
              ? payload.verification_report_id
              : typeof payload.escalation_packet_id === "string"
                ? payload.escalation_packet_id
                : typeof payload.wiki_edit_proposal_id === "string"
                  ? payload.wiki_edit_proposal_id
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

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : []
}

function packetResponseControlRef(packet: Record<string, unknown> | undefined): string | undefined {
  const ref = String(packet?.response_control_ref ?? "").trim()
  return ref || undefined
}

function packetSelectedRefs(packet: Record<string, unknown> | undefined, key: string): string[] {
  return asStringArray(packet?.[key])
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
  const responseControlRef = packetResponseControlRef(packet) ?? state.response_control_ref
  const selectedPoolRefs =
    packetSelectedRefs(packet, "selected_knowledge_pool_refs").length > 0
      ? packetSelectedRefs(packet, "selected_knowledge_pool_refs")
      : state.selected_knowledge_pool_refs
  const selectedModuleRefs =
    packetSelectedRefs(packet, "selected_module_refs").length > 0
      ? packetSelectedRefs(packet, "selected_module_refs")
      : state.selected_module_refs
  const selectedTechniqueRefs =
    packetSelectedRefs(packet, "selected_technique_refs").length > 0
      ? packetSelectedRefs(packet, "selected_technique_refs")
      : state.selected_technique_refs
  const selectedTheoryRefs =
    packetSelectedRefs(packet, "selected_theory_refs").length > 0
      ? packetSelectedRefs(packet, "selected_theory_refs")
      : state.selected_theory_refs
  const toolResults = state.required_tool_results && state.required_tool_results.length > 0
    ? `Required tool results:\n${JSON.stringify(state.required_tool_results, null, 2)}`
    : ""
  const wikiOverlayContext =
    typeof packet.wiki_overlay_context === "string"
      ? packet.wiki_overlay_context
      : state.wiki_overlay_context
  return [
    `Objective: ${String(packet.objective ?? latestUserContent(state.messages))}`,
    packet.context_summary ? `Context summary:\n${String(packet.context_summary)}` : "",
    constraints.length > 0 ? `Constraints:\n- ${constraints.join("\n- ")}` : "",
    acceptance.length > 0 ? `Acceptance criteria:\n- ${acceptance.join("\n- ")}` : "",
    implementationHints.length > 0
      ? `Implementation hints:\n- ${implementationHints.join("\n- ")}`
      : "",
    responseControlRef ? `Response control ref: ${responseControlRef}` : "",
    selectedPoolRefs.length > 0
      ? `Selected knowledge pools:\n- ${selectedPoolRefs.join("\n- ")}`
      : "",
    selectedModuleRefs.length > 0
      ? `Selected modules:\n- ${selectedModuleRefs.join("\n- ")}`
      : "",
    selectedTechniqueRefs.length > 0
      ? `Selected techniques:\n- ${selectedTechniqueRefs.join("\n- ")}`
      : "",
    selectedTheoryRefs.length > 0
      ? `Selected theory basis:\n- ${selectedTheoryRefs.join("\n- ")}`
      : "",
    wikiOverlayContext ? `Wiki context overlay:\n${wikiOverlayContext}` : "",
    toolResults,
    "Use only the task packet, response-control refs, and artifact refs as governing context.",
  ]
    .filter(Boolean)
    .join("\n\n")
}

function workspaceRootFromState(
  state: EngineeringWorkflowStateType,
): string | undefined {
  const context = state.request_context
  const workspace = (context?.workspace as Record<string, unknown> | undefined) ?? undefined
  if (typeof workspace?.worktree_path === "string" && workspace.worktree_path.trim().length > 0) {
    return workspace.worktree_path
  }
  if (typeof context?.workspace_root === "string" && context.workspace_root.trim().length > 0) {
    return context.workspace_root
  }
  if (typeof context?.cwd === "string" && context.cwd.trim().length > 0) {
    return context.cwd
  }
  return undefined
}

function intakeEngineering(_state: EngineeringWorkflowStateType): Partial<EngineeringWorkflowStateType> {
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
    const responseMode =
      typeof intake.response_mode === "string" ? intake.response_mode : state.response_mode
    const responseControlAssessment =
      intake.response_control_assessment && typeof intake.response_control_assessment === "object"
        ? (intake.response_control_assessment as Record<string, unknown>)
        : undefined
    const responseControlRef =
      typeof intake.response_control_ref === "string"
        ? intake.response_control_ref
        : state.response_control_ref
    const selectedKnowledgePoolRefs = Array.isArray(intake.selected_knowledge_pool_refs)
      ? (intake.selected_knowledge_pool_refs as string[])
      : state.selected_knowledge_pool_refs
    const selectedModuleRefs = Array.isArray(intake.selected_module_refs)
      ? (intake.selected_module_refs as string[])
      : state.selected_module_refs
    const selectedTechniqueRefs = Array.isArray(intake.selected_technique_refs)
      ? (intake.selected_technique_refs as string[])
      : state.selected_technique_refs
    const selectedTheoryRefs = Array.isArray(intake.selected_theory_refs)
      ? (intake.selected_theory_refs as string[])
      : state.selected_theory_refs
    const knowledgePoolAssessment =
      intake.knowledge_pool_assessment && typeof intake.knowledge_pool_assessment === "object"
        ? (intake.knowledge_pool_assessment as Record<string, unknown>)
        : undefined
    const knowledgeRoleContexts =
      intake.knowledge_role_contexts && typeof intake.knowledge_role_contexts === "object"
        ? (intake.knowledge_role_contexts as Record<string, Record<string, unknown>>)
        : undefined
    const knowledgePoolAssessmentRef =
      typeof intake.knowledge_pool_assessment_ref === "string"
        ? intake.knowledge_pool_assessment_ref
        : undefined
    const knowledgePoolCoverage =
      typeof intake.knowledge_pool_coverage === "string"
        ? intake.knowledge_pool_coverage
        : undefined
    const knowledgeCandidateRefs = Array.isArray(intake.knowledge_candidate_refs)
      ? (intake.knowledge_candidate_refs as string[])
      : []
    const knowledgeRoleContextRefs = Array.isArray(intake.knowledge_role_context_refs)
      ? (intake.knowledge_role_context_refs as string[])
      : []
    const knowledgeGaps = Array.isArray(intake.knowledge_gaps)
      ? (intake.knowledge_gaps as string[])
      : []
    const knowledgeRequired =
      typeof intake.knowledge_required === "boolean"
        ? intake.knowledge_required
        : undefined
    const escalationPacket =
      intake.escalation_packet && typeof intake.escalation_packet === "object"
        ? (intake.escalation_packet as Record<string, unknown>)
        : undefined
    const wikiOverlayContext =
      typeof intake.wiki_overlay_context === "string" ? intake.wiki_overlay_context : undefined
    const wikiEditProposals = Array.isArray(intake.wiki_edit_proposals)
      ? (intake.wiki_edit_proposals as Record<string, unknown>[])
      : []
    const wikiEditProposalRefs = Array.isArray(intake.wiki_edit_proposal_refs)
      ? (intake.wiki_edit_proposal_refs as string[])
      : []

    const artifacts: Array<Record<string, unknown>> = []
    if (knowledgePoolAssessment) {
      artifacts.push(
        typedArtifact(
          "KNOWLEDGE_POOL_ASSESSMENT",
          knowledgePoolAssessment,
          [],
          "agent_platform.engineering_graph.intake",
          "local_general_model",
        ),
      )
    }
    if (responseControlAssessment) {
      artifacts.push(
        typedArtifact(
          "RESPONSE_CONTROL_ASSESSMENT",
          responseControlAssessment,
          [...selectedKnowledgePoolRefs, ...selectedModuleRefs, ...selectedTechniqueRefs, ...selectedTheoryRefs],
          "agent_platform.engineering_graph.intake",
          "local_general_model",
        ),
      )
    }
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
    if (knowledgeRoleContexts) {
      for (const payload of Object.values(knowledgeRoleContexts)) {
        artifacts.push(
          typedArtifact(
            "ROLE_CONTEXT_BUNDLE",
            payload,
            Array.isArray(payload.source_artifact_refs)
              ? (payload.source_artifact_refs as string[])
              : [],
            "agent_platform.engineering_graph.intake",
            "local_general_model",
          ),
        )
      }
    }
    if (escalationPacket) {
      artifacts.push(
        typedArtifact(
          "ESCALATION_RECORD",
          escalationPacket,
          Array.isArray(escalationPacket.supporting_artifact_refs)
            ? (escalationPacket.supporting_artifact_refs as string[])
            : [],
          "agent_platform.engineering_graph.intake",
          "strategic_reviewer",
        ),
      )
    }
    for (const proposal of wikiEditProposals) {
      artifacts.push(
        typedArtifact(
          "WIKI_EDIT_PROPOSAL",
          proposal,
          Array.isArray(proposal.provenance_refs)
            ? (proposal.provenance_refs as string[])
            : [],
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
        response_mode: responseMode,
        response_control_ref: responseControlRef,
        selected_knowledge_pool_refs: selectedKnowledgePoolRefs,
        selected_module_refs: selectedModuleRefs,
        selected_technique_refs: selectedTechniqueRefs,
        selected_theory_refs: selectedTheoryRefs,
        knowledge_pool_assessment: knowledgePoolAssessment,
        knowledge_pool_assessment_ref: knowledgePoolAssessmentRef,
        knowledge_pool_coverage: knowledgePoolCoverage,
        knowledge_candidate_refs: knowledgeCandidateRefs,
        knowledge_role_contexts: knowledgeRoleContexts,
        knowledge_role_context_refs: knowledgeRoleContextRefs,
        knowledge_gaps: knowledgeGaps,
        knowledge_required: knowledgeRequired,
        wiki_overlay_context: wikiOverlayContext,
        wiki_edit_proposals: wikiEditProposals,
        wiki_edit_proposal_refs: wikiEditProposalRefs,
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
        response_mode: responseMode,
        response_control_ref: responseControlRef,
        selected_knowledge_pool_refs: selectedKnowledgePoolRefs,
        selected_module_refs: selectedModuleRefs,
        selected_technique_refs: selectedTechniqueRefs,
        selected_theory_refs: selectedTheoryRefs,
        knowledge_pool_assessment: knowledgePoolAssessment,
        knowledge_pool_assessment_ref: knowledgePoolAssessmentRef,
        knowledge_pool_coverage: knowledgePoolCoverage,
        knowledge_candidate_refs: knowledgeCandidateRefs,
        knowledge_role_contexts: knowledgeRoleContexts,
        knowledge_role_context_refs: knowledgeRoleContextRefs,
        knowledge_gaps: knowledgeGaps,
        knowledge_required: knowledgeRequired,
        wiki_overlay_context: wikiOverlayContext,
        wiki_edit_proposals: wikiEditProposals,
        wiki_edit_proposal_refs: wikiEditProposalRefs,
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

    if (status === "ESCALATED") {
      const finalResponse =
        escalationPacket && Array.isArray(escalationPacket.unresolved_items)
          ? `Engineering escalation required:\n- ${(
              escalationPacket.unresolved_items as string[]
            ).join("\n- ")}`
          : "Engineering escalation required before governed execution can continue."
      return {
        dossier_snapshot: dossierSnapshot,
        engineering_session_id: intake.engineering_session_id as string | undefined,
        engagement_mode: engagementMode,
        engagement_mode_source: engagementModeSource,
        engagement_mode_confidence: engagementModeConfidence,
        engagement_mode_reasons: engagementModeReasons,
        minimum_engagement_mode: minimumEngagementMode,
        pending_mode_change: pendingModeChange,
        response_mode: responseMode,
        response_control_ref: responseControlRef,
        selected_knowledge_pool_refs: selectedKnowledgePoolRefs,
        selected_module_refs: selectedModuleRefs,
        selected_technique_refs: selectedTechniqueRefs,
        selected_theory_refs: selectedTheoryRefs,
        knowledge_pool_assessment: knowledgePoolAssessment,
        knowledge_pool_assessment_ref: knowledgePoolAssessmentRef,
        knowledge_pool_coverage: knowledgePoolCoverage,
        knowledge_candidate_refs: knowledgeCandidateRefs,
        knowledge_role_contexts: knowledgeRoleContexts,
        knowledge_role_context_refs: knowledgeRoleContextRefs,
        knowledge_gaps: knowledgeGaps,
        knowledge_required: knowledgeRequired,
        wiki_overlay_context: wikiOverlayContext,
        wiki_edit_proposals: wikiEditProposals,
        wiki_edit_proposal_refs: wikiEditProposalRefs,
        lifecycle_reason: "awaiting_strategic_review",
        lifecycle_detail: { knowledge_gaps: knowledgeGaps.length },
        problem_brief: problemBrief,
        problem_brief_ref: intake.problem_brief_ref as string | undefined,
        engineering_state: engineeringState,
        engineering_state_ref: intake.engineering_state_ref as string | undefined,
        escalation_packet: escalationPacket,
        required_gates: requiredGates,
        clarification_questions: clarificationQuestions,
        ready_for_task_decomposition: false,
        final_response: finalResponse,
        verification_outcome: "ESCALATE",
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
        response_mode: responseMode,
        response_control_ref: responseControlRef,
        selected_knowledge_pool_refs: selectedKnowledgePoolRefs,
        selected_module_refs: selectedModuleRefs,
        selected_technique_refs: selectedTechniqueRefs,
        selected_theory_refs: selectedTheoryRefs,
        knowledge_pool_assessment: knowledgePoolAssessment,
        knowledge_pool_assessment_ref: knowledgePoolAssessmentRef,
        knowledge_pool_coverage: knowledgePoolCoverage,
        knowledge_candidate_refs: knowledgeCandidateRefs,
        knowledge_role_contexts: knowledgeRoleContexts,
        knowledge_role_context_refs: knowledgeRoleContextRefs,
        knowledge_gaps: knowledgeGaps,
        knowledge_required: knowledgeRequired,
        wiki_overlay_context: wikiOverlayContext,
        wiki_edit_proposals: wikiEditProposals,
        wiki_edit_proposal_refs: wikiEditProposalRefs,
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
        verification_outcome: "BLOCKED",
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
      response_mode: responseMode,
      response_control_ref: responseControlRef,
      selected_knowledge_pool_refs: selectedKnowledgePoolRefs,
      selected_module_refs: selectedModuleRefs,
      selected_technique_refs: selectedTechniqueRefs,
      selected_theory_refs: selectedTheoryRefs,
      knowledge_pool_assessment: knowledgePoolAssessment,
      knowledge_pool_assessment_ref: knowledgePoolAssessmentRef,
      knowledge_pool_coverage: knowledgePoolCoverage,
      knowledge_candidate_refs: knowledgeCandidateRefs,
      knowledge_role_contexts: knowledgeRoleContexts,
      knowledge_role_context_refs: knowledgeRoleContextRefs,
      knowledge_gaps: knowledgeGaps,
      knowledge_required: knowledgeRequired,
      wiki_overlay_context: wikiOverlayContext,
      wiki_edit_proposals: wikiEditProposals,
      wiki_edit_proposal_refs: wikiEditProposalRefs,
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

/**
 * Node factory for executing an active TaskPacket.
 * 
 * Why: This is the primary execution boundary. It takes the deterministic 
 * TaskPacket generated by the intake phase and dispatches it to the runtime 
 * engine. Depending on the `selected_executor` in the packet, this may trigger 
 * a multi-agent orchestration, a raw coding model run, or a domain-specific 
 * deterministic adapter.
 */
function buildExecuteTaskPacket(cfg: PlatformConfig, engine: OrchestrationEngine) {
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
    const responseControlRef = packetResponseControlRef(packet) ?? state.response_control_ref
    const selectedPoolRefs =
      packetSelectedRefs(packet, "selected_knowledge_pool_refs").length > 0
        ? packetSelectedRefs(packet, "selected_knowledge_pool_refs")
        : state.selected_knowledge_pool_refs
    const selectedTheoryRefs =
      packetSelectedRefs(packet, "selected_theory_refs").length > 0
        ? packetSelectedRefs(packet, "selected_theory_refs")
        : state.selected_theory_refs
    const selectedModuleRefs =
      packetSelectedRefs(packet, "selected_module_refs").length > 0
        ? packetSelectedRefs(packet, "selected_module_refs")
        : state.selected_module_refs
    const knowledgeRequired = state.knowledge_required === true || selectedPoolRefs.length > 0
    if (knowledgeRequired && !responseControlRef) {
      return {
        final_response:
          "Strict engineering execution blocked: active packet is missing response_control_ref.",
        verification_outcome: "BLOCKED",
        lifecycle_reason: "governance_gate",
        lifecycle_detail: {
          reason: "response_control_ref_missing",
          active_task_packet_ref: state.active_task_packet_ref,
        },
        current_step: "complete",
      }
    }
    if (knowledgeRequired && selectedPoolRefs.length === 0) {
      return {
        final_response:
          "Strict engineering execution blocked: active packet is missing selected_knowledge_pool_refs.",
        verification_outcome: "BLOCKED",
        lifecycle_reason: "governance_gate",
        lifecycle_detail: {
          reason: "selected_knowledge_pool_refs_missing",
          active_task_packet_ref: state.active_task_packet_ref,
        },
        current_step: "complete",
      }
    }
    if (knowledgeRequired && selectedTheoryRefs.length === 0) {
      return {
        final_response:
          "Strict engineering execution blocked: active packet is missing selected_theory_refs.",
        verification_outcome: "BLOCKED",
        lifecycle_reason: "governance_gate",
        lifecycle_detail: {
          reason: "selected_theory_refs_missing",
          active_task_packet_ref: state.active_task_packet_ref,
        },
        current_step: "complete",
      }
    }
    if (selectedExecutor === "coding_model" && selectedModuleRefs.length === 0) {
      return {
        final_response:
          "Strict engineering execution blocked: coding packet is missing selected_module_refs.",
        verification_outcome: "BLOCKED",
        lifecycle_reason: "governance_gate",
        lifecycle_detail: {
          reason: "selected_module_refs_missing",
          active_task_packet_ref: state.active_task_packet_ref,
        },
        current_step: "complete",
      }
    }

    const inputRefs = packetInputRefs(packet)
    const artifactType = packetOutputArtifactType(packet)
    const prompt = packetPrompt(packet, state)
    const workspaceRoot = workspaceRootFromState(state)

    try {
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
      }

      const systemPrompt =
        selectedExecutor === "local_general_model"
          ? "You are the governed local-general executor. Synthesize only from the packet and referenced artifacts; do not invent missing evidence or mutate repositories."
          : "You are the strategic reviewer for a typed engineering escalation packet. Return compact decision guidance only."
      const routing = resolveWorkflowModelRouting(cfg, {}, state.workflow_config ?? {})

      const execution = await engine.runGovernedEngineering({
        selectedExecutor,
        title: String(packet.objective ?? latestUserContent(state.messages)),
        prompt:
          selectedExecutor === "strategic_reviewer" && state.escalation_packet
            ? JSON.stringify(
                {
                  type: "ESCALATION_PACKET",
                  escalation_packet: state.escalation_packet,
                  knowledge_pool_assessment_ref: state.knowledge_pool_assessment_ref,
                  response_control_ref: state.response_control_ref,
                  selected_knowledge_pool_refs: state.selected_knowledge_pool_refs,
                  selected_module_refs: state.selected_module_refs,
                  selected_technique_refs: state.selected_technique_refs,
                  selected_theory_refs: state.selected_theory_refs,
                },
                null,
                2,
              )
            : prompt,
        systemPrompt,
        workspaceRoot,
        packet,
        toolNames: [],
        model: routing.model,
        provider: routing.provider,
        baseURL: routing.baseURL,
        apiKey: routing.apiKey,
        claw:
          selectedExecutor === "coding_model"
            ? {
                workspaceRoot,
                objective: String(packet.objective ?? latestUserContent(state.messages)),
                scope: String(
                  packet.context_summary ??
                    ((packet.code_guidance as Record<string, unknown> | undefined)?.target_paths ??
                      []).toString() ??
                    "governed engineering task",
                ),
                repo:
                  workspaceRoot?.split("/").filter(Boolean).at(-1) ??
                  String(packet.task_packet_id ?? "workspace"),
                branchPolicy: "use the governed worktree only",
                acceptanceTests: Array.isArray(packet.validation_requirements)
                  ? (packet.validation_requirements as string[])
                  : [],
                commitPolicy: "leave changes ready for deterministic verification",
                reportingContract:
                  "Persist execution through Claw manifest/output files and summarize changes only.",
                escalationPolicy:
                  "Stop on destructive ambiguity and surface blockers through the Claw manifest.",
                prompt,
              }
            : undefined,
      })

      if (selectedExecutor === "deterministic_validator") {
        return {
          final_response: execution.output,
          current_step: "verification",
        }
      }

      const payload = {
        schema_version: "1.0.0",
        generated_from_task_packet_id: packet.task_packet_id,
        selected_executor: selectedExecutor,
        text: execution.output,
        model_id_resolved: execution.model,
        usage: execution.usage,
        structured_output: execution.structuredOutput ?? {},
        execution_artifacts: execution.artifacts?.map((artifact) => ({
          name: artifact.name,
          path: artifact.path,
          kind: artifact.kind,
        })),
        created_at: new Date().toISOString(),
      }
      const artifact = typedArtifact(
        artifactType,
        payload,
        inputRefs,
        `agent_platform.engineering_graph.execute.${selectedExecutor}`,
        selectedExecutor,
      )
      await persistRunEvent(cfg, state, {
        message: "engineering_workflow:execute_packet",
        details: {
          selected_executor: selectedExecutor,
          active_task_packet_ref: state.active_task_packet_ref,
          runtime: execution.runtime,
        },
        artifacts: [artifact],
      })
      return {
        final_response: execution.output,
        generated_artifacts: [artifact],
        generated_artifact_refs: [artifactRefFromEnvelope(artifact)].filter(
          Boolean,
        ) as string[],
        cost_ledger_entries:
          execution.usage && execution.model
            ? [
                {
                  component: "engineering_workflow.execute_packet",
                  model: execution.model,
                  tokens_in: execution.usage.prompt_tokens,
                  tokens_out: execution.usage.completion_tokens,
                  duration_ms: execution.usage.latency_ms ?? 0,
                  task_packet_id: state.active_task_packet_id,
                },
              ]
            : [],
        current_step: "verification",
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

/**
 * Node factory for the deterministic verification gate.
 * 
 * Why: Every governed execution must be verified against the `acceptance_criteria` 
 * and `validation_requirements` defined in the packet. This node executes 
 * deterministic checks (e.g., unit tests, compiler checks) and yields a 
 * `VERIFICATION_REPORT`. If the report outcome is `REWORK`, the graph cycles 
 * back for revision; if `ESCALATE`, it moves to strategic review.
 */
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
    const activeResponseControlRef =
      packetResponseControlRef(state.task_packet) ?? state.response_control_ref
    const activePoolRefs =
      packetSelectedRefs(state.task_packet, "selected_knowledge_pool_refs").length > 0
        ? packetSelectedRefs(state.task_packet, "selected_knowledge_pool_refs")
        : state.selected_knowledge_pool_refs
    const activeModuleRefs =
      packetSelectedRefs(state.task_packet, "selected_module_refs").length > 0
        ? packetSelectedRefs(state.task_packet, "selected_module_refs")
        : state.selected_module_refs
    const activeTechniqueRefs =
      packetSelectedRefs(state.task_packet, "selected_technique_refs").length > 0
        ? packetSelectedRefs(state.task_packet, "selected_technique_refs")
        : state.selected_technique_refs
    const activeTheoryRefs =
      packetSelectedRefs(state.task_packet, "selected_theory_refs").length > 0
        ? packetSelectedRefs(state.task_packet, "selected_theory_refs")
        : state.selected_theory_refs
    const validatedRefs = Array.from(
      new Set(
        [
          ...packetInputRefs(sourcePacket),
          ...generatedArtifactRefs,
          state.problem_brief_ref,
          state.knowledge_pool_assessment_ref,
          activeResponseControlRef,
          ...activePoolRefs,
          ...activeModuleRefs,
          ...activeTechniqueRefs,
          ...activeTheoryRefs,
          state.engineering_state_ref,
        ].filter(Boolean) as string[],
      ),
    )
    const gateResults: Array<Record<string, unknown>> = []
    const blockingFindings: Array<Record<string, unknown>> = []
    const knowledgeRequired = state.knowledge_required === true || activePoolRefs.length > 0

    if (knowledgeRequired) {
      const hasResponseControlRef = Boolean(activeResponseControlRef)
      gateResults.push({
        gate_id: "response_control_ref_present",
        gate_kind: "policy",
        status: hasResponseControlRef ? "PASS" : "FAIL",
        detail: hasResponseControlRef
          ? "Response-control ref is present."
          : "Response-control ref is missing for a knowledge-required packet.",
      })
      if (!hasResponseControlRef) {
        blockingFindings.push({
          code: "RESPONSE_CONTROL_REF_MISSING",
          severity: "high",
          artifact_ref: state.active_task_packet_ref ?? null,
        })
      }

      gateResults.push({
        gate_id: "selected_knowledge_pools_present",
        gate_kind: "policy",
        status: activePoolRefs.length > 0 ? "PASS" : "FAIL",
        detail:
          activePoolRefs.length > 0
            ? "Selected knowledge-pool refs are present."
            : "Selected knowledge-pool refs are missing for a knowledge-required packet.",
      })
      if (activePoolRefs.length === 0) {
        blockingFindings.push({
          code: "SELECTED_KNOWLEDGE_POOL_REFS_MISSING",
          severity: "high",
          artifact_ref: state.active_task_packet_ref ?? null,
        })
      }

      gateResults.push({
        gate_id: "selected_theory_refs_present",
        gate_kind: "policy",
        status: activeTheoryRefs.length > 0 ? "PASS" : "FAIL",
        detail:
          activeTheoryRefs.length > 0
            ? "Selected theory refs are present."
            : "Selected theory refs are missing for a knowledge-required packet.",
      })
      if (activeTheoryRefs.length === 0) {
        blockingFindings.push({
          code: "SELECTED_THEORY_REFS_MISSING",
          severity: "high",
          artifact_ref: state.active_task_packet_ref ?? null,
        })
      }
    }

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
      knowledge_pool_assessment_ref: state.knowledge_pool_assessment_ref,
      response_control_ref: state.response_control_ref,
      selected_knowledge_pool_refs: state.selected_knowledge_pool_refs,
      selected_module_refs: state.selected_module_refs,
      selected_technique_refs: state.selected_technique_refs,
      selected_theory_refs: state.selected_theory_refs,
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

/**
 * Final node to synthesize all outputs into a human-readable final response.
 * 
 * Why: This aggregates data from the verification reports, strategic reviews, 
 * and generated artifacts to provide the operator with a high-level summary 
 * of the governed run's outcome.
 */
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
  engine: OrchestrationEngine,
  apiBrainCall?: (packet: string) => Promise<string>,
) {
  const engineeringIntake = buildEngineeringIntake(cfg)
  const executeTaskPacket = buildExecuteTaskPacket(cfg, engine)
  const verification = buildVerificationEngineering(cfg)
  const typedEscalation = buildTypedEscalation(cfg, apiBrainCall)

  const graph = new StateGraph(EngineeringWorkflowAnnotation)
    .addNode("intake", intakeEngineering)
    .addNode("engineering_intake", engineeringIntake)
    .addNode("execute_packet", executeTaskPacket)
    .addNode("verification", verification)
    .addNode("typed_escalation", typedEscalation)
    .addNode("synthesize", synthesizeEngineering)
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
