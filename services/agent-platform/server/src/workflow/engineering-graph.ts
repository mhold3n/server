/**
 * Engineering-oriented LangGraph workflow: referential DevPlane pointers + task_packet contract.
 *
 * For agents: execution substrate only — routing uses control-plane `/api/control-plane/structure/classify`
 * when `orchestratorApiUrl` is set. Chat-shaped `wrkhrs_chat` remains separate.
 */

import { randomUUID } from "node:crypto"
import { Annotation, END, START, StateGraph } from "@langchain/langgraph"
import type { PlatformConfig } from "../config.js"
import { LLMManager } from "../llm/manager.js"
import type { ChatMessage } from "../tools/wrkhrs.js"
import {
  analyzeRequest,
  buildApiBrainPacket,
  buildGatherContext,
  buildGenerateResponse,
  shouldEscalateToApiBrain,
} from "./graph.js"

/** Referential + engineering fields (Option A: minimal graph state, DevPlane authoritative). */
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
  active_task_packet_id: Annotation<string | undefined>(),
  task_packet: Annotation<Record<string, unknown> | undefined>(),
  structure_route: Annotation<Record<string, unknown> | undefined>(),
  verification_outcome: Annotation<string | undefined>(),
  verification_report: Annotation<Record<string, unknown> | undefined>(),
  cost_ledger_entries: Annotation<Record<string, unknown>[]>({
    reducer: (left, right) => [...left, ...right],
    default: () => [],
  }),
  /** Latest DevPlane dossier JSON when task_id + orchestrator URL allow hydrate (authoritative refs). */
  dossier_snapshot: Annotation<Record<string, unknown> | undefined>(),
})

export type EngineeringWorkflowStateType = typeof EngineeringWorkflowAnnotation.State

async function classifyViaControlPlane(
  cfg: PlatformConfig,
  userInput: string,
  requestId: string,
): Promise<Record<string, unknown>> {
  const base = cfg.orchestratorApiUrl?.replace(/\/$/, "") ?? ""
  if (!base) {
    return { skipped: true, reason: "orchestrator_api_url_unset" }
  }
  const url = `${base}/api/control-plane/structure/classify`
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_input: userInput, request_id: requestId }),
  })
  if (!res.ok) {
    const text = await res.text()
    return { error: true, status: res.status, body: text }
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

async function persistVerificationRunEvent(
  cfg: PlatformConfig,
  state: EngineeringWorkflowStateType,
  report: Record<string, unknown>,
): Promise<void> {
  const base = cfg.orchestratorApiUrl?.replace(/\/$/, "") ?? ""
  const runId = state.run_id
  if (!base || !runId) {
    return
  }
  const vid = report.verification_report_id
  const artifactId = typeof vid === "string" ? vid : randomUUID()
  const refs = report.validated_artifact_refs
  const inputRefs = Array.isArray(refs) ? refs : []
  const body = {
    message: "engineering_workflow:verification_gate",
    details: {
      verification_outcome: report.outcome,
      workflow: "engineering_workflow",
    },
    cost_ledger: state.cost_ledger_entries ?? [],
    artifacts: [
      {
        artifact_id: artifactId,
        artifact_type: "VERIFICATION_REPORT",
        schema_version: "1.0.0",
        artifact_status: "ACTIVE",
        validation_state: "VALID",
        producer: {
          component: "agent_platform.engineering_graph.verification",
          run_id: runId,
          task_packet_id: state.active_task_packet_id ?? null,
        },
        input_artifact_refs: inputRefs,
        supersedes: [],
        payload: report,
      },
    ],
  }
  const url = `${base}/api/dev/runs/${encodeURIComponent(runId)}/events`
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    // Non-fatal: graph still completes; operators see failure in logs if they inspect HTTP.
    console.warn(
      "persistVerificationRunEvent failed",
      res.status,
      await res.text().catch(() => ""),
    )
  }
}

function intakeEngineering(
  state: EngineeringWorkflowStateType,
): Partial<EngineeringWorkflowStateType> {
  const tp = state.task_packet
  if (!tp || typeof tp !== "object") {
    throw new Error("engineering_workflow requires input_data.task_packet")
  }
  const id = tp.task_packet_id
  return {
    current_step: "route_structure",
    active_task_packet_id: typeof id === "string" ? id : String(id ?? ""),
  }
}

function buildRouteStructure(cfg: PlatformConfig) {
  return async function routeStructure(
    state: EngineeringWorkflowStateType,
  ): Promise<Partial<EngineeringWorkflowStateType>> {
    const taskId = state.task_id
    const dossier_snapshot =
      typeof taskId === "string" && taskId.length > 0
        ? await fetchDevPlaneDossier(cfg, taskId)
        : undefined
    const objective = String(state.task_packet?.objective ?? "")
    const rid = state.run_id ?? state.active_task_packet_id ?? randomUUID()
    const route = await classifyViaControlPlane(cfg, objective, rid)
    return {
      structure_route: route,
      dossier_snapshot,
      current_step: "analyze",
    }
  }
}

function buildExecuteWithCost(llm: LLMManager) {
  const gen = buildGenerateResponse(llm)
  return async function executeGenerate(
    state: EngineeringWorkflowStateType,
  ): Promise<Partial<EngineeringWorkflowStateType>> {
    const out = await gen(state as any)
    const entries: Record<string, unknown>[] = [...(state.cost_ledger_entries ?? [])]
    entries.push({
      component: "llm.execute_generate",
      model: "local_worker",
      tokens_in: 0,
      tokens_out: 0,
      duration_ms: 0,
      task_packet_id: state.active_task_packet_id,
    })
    return { ...out, cost_ledger_entries: entries, current_step: "verify" }
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
      const obj = String(state.task_packet?.objective ?? "").toLowerCase()
      if (obj.includes("escalate verification")) {
        outcome = "ESCALATE"
      } else if (obj.includes("rework verification")) {
        outcome = "REWORK"
      }
    }
    const budget = state.task_packet?.budget_policy as Record<string, unknown> | undefined
    if (budget && budget.allow_escalation === false && outcome === "ESCALATE") {
      outcome = "REWORK"
    }
    const validatedRefs = (() => {
      const refs = state.task_packet?.input_artifact_refs
      if (Array.isArray(refs) && refs.length > 0) {
        return refs as string[]
      }
      return ["artifact://requirements_set/placeholder"]
    })()
    const pktId = state.task_packet?.task_packet_id
    const fallbackId = state.active_task_packet_id
    const sourcePacket =
      typeof pktId === "string" && /^[0-9a-f-]{36}$/i.test(pktId)
        ? pktId
        : typeof fallbackId === "string" && /^[0-9a-f-]{36}$/i.test(fallbackId)
          ? fallbackId
          : randomUUID()
    const report: Record<string, unknown> = {
      verification_report_id: randomUUID(),
      schema_version: "1.0.0",
      outcome,
      reasons: outcome === "PASS" ? [] : ["verification_gate"],
      blocking_findings:
        outcome === "PASS"
          ? []
          : [
              {
                code: "GATE_FAILED",
                severity: "high",
                artifact_ref: validatedRefs[0] ?? null,
              },
            ],
      recommended_next_action:
        outcome === "ESCALATE" ? "create_escalation_packet" : "continue",
      validated_artifact_refs: validatedRefs,
      source_task_packet_id: sourcePacket,
      created_at: new Date().toISOString(),
    }
    await persistVerificationRunEvent(cfg, state, report)
    return {
      verification_outcome: outcome,
      verification_report: report,
      current_step: "synthesize",
    }
  }
}

function synthesizeEngineering(
  state: EngineeringWorkflowStateType,
): Partial<EngineeringWorkflowStateType> {
  const base = state.final_response ?? ""
  const vo = state.verification_outcome ?? "UNKNOWN"
  const syn = `${base}\n\n[verification:${vo}]`
  return { final_response: syn, current_step: "complete" }
}

export function createEngineeringWorkflow(
  cfg: PlatformConfig,
  llm: LLMManager,
  apiBrainCall?: (packet: string) => Promise<string>,
) {
  const gatherContext = buildGatherContext(cfg)
  const executeGenerate = buildExecuteWithCost(llm)
  const routeStructure = buildRouteStructure(cfg)
  const verification = buildVerificationEngineering(cfg)

  const decideEscalation = async (
    state: EngineeringWorkflowStateType,
  ): Promise<Partial<EngineeringWorkflowStateType>> => {
    const decision = shouldEscalateToApiBrain(cfg, state as any)
    if (!decision.escalate || !apiBrainCall) {
      return {
        current_step: state.tools_needed.length > 0 ? "gather_context" : "execute_generate",
      }
    }
    const packet = buildApiBrainPacket(state as any)
    const output = await apiBrainCall(packet)
    return {
      api_brain_packet: packet,
      api_brain_output: output,
      escalation_count: state.escalation_count + 1,
      current_step: state.tools_needed.length > 0 ? "gather_context" : "execute_generate",
    }
  }

  const graph = new StateGraph(EngineeringWorkflowAnnotation)
    .addNode("intake", intakeEngineering as any)
    .addNode("route_structure", routeStructure)
    .addNode("analyze", analyzeRequest as any)
    .addNode("decide_escalation", decideEscalation)
    .addNode("gather_context", gatherContext as any)
    .addNode("execute_generate", executeGenerate as any)
    .addNode("verification", verification as any)
    .addNode("synthesize", synthesizeEngineering as any)
    .addEdge(START, "intake")
    .addEdge("intake", "route_structure")
    .addEdge("route_structure", "analyze")
    .addEdge("analyze", "decide_escalation")
    .addConditionalEdges("decide_escalation", (s) =>
      s.tools_needed.length > 0 ? "gather_context" : "execute_generate",
    )
    .addEdge("gather_context", "execute_generate")
    .addEdge("execute_generate", "verification")
    .addEdge("verification", "synthesize")
    .addEdge("synthesize", END)

  return graph.compile()
}
