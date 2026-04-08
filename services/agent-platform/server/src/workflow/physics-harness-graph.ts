/**
 * v1 engineering physics harness: INTAKE → map → solve → verify → SYNTHESIZE.
 *
 * For agents: calls model-runtime HTTP only; numbers come from /solve/mechanics (engineering-core).
 */

import { randomUUID } from "node:crypto"
import { Annotation, END, START, StateGraph } from "@langchain/langgraph"
import type { PlatformConfig } from "../config.js"
import {
  postInferGeneral,
  postSolveMechanics,
  postSolveVerify,
  type OrchestrationPacket,
} from "../llm/model-runtime-client.js"

export const PhysicsHarnessAnnotation = Annotation.Root({
  user_prompt: Annotation<string>(),
  root_packet_id: Annotation<string | undefined>(),
  intake_infer: Annotation<Record<string, unknown> | undefined>(),
  solve_request: Annotation<Record<string, unknown> | undefined>(),
  engineering_report: Annotation<Record<string, unknown> | undefined>(),
  verification_outcome: Annotation<Record<string, unknown> | undefined>(),
  synthesis_infer: Annotation<Record<string, unknown> | undefined>(),
  harness_error: Annotation<string | undefined>(),
  current_step: Annotation<string>(),
})

export type PhysicsHarnessState = typeof PhysicsHarnessAnnotation.State

function baseRoutingMetadata() {
  return {
    selected_executor: "GENERAL_LOCAL",
    selection_reason_code: "OPERATION_MATCH",
    selection_reason_detail: "engineering_physics_v1",
    policy_version: "v1",
    budget_policy: { allow_escalation: false, max_tokens: 4096 },
  }
}

function buildIntakePacket(rootId: string, objective: string): OrchestrationPacket {
  return {
    packet_id: rootId,
    packet_class: "ORCHESTRATION",
    operation: "INTAKE",
    objective,
    context_summary: "",
    constraints: [],
    expected_output: {
      artifact_type: "PROBLEM_BRIEF",
      schema_id: "urn:claw:schema:problem-brief:1.0",
      cardinality: "ONE",
      allow_partial: false,
    },
    routing_metadata: baseRoutingMetadata(),
    provenance: {
      source_stage: "INTAKE",
      parent_packet_id: null,
      input_artifact_refs: [],
      decision_ref: null,
    },
  }
}

function buildSynthesizePacket(parentId: string, objective: string): OrchestrationPacket {
  return {
    packet_id: randomUUID(),
    packet_class: "ORCHESTRATION",
    operation: "SYNTHESIZE",
    objective,
    context_summary: "Use verified engineering_report only for numerics.",
    constraints: ["Do not invent accelerations or forces not in the report"],
    expected_output: {
      artifact_type: "PROBLEM_BRIEF",
      schema_id: "urn:claw:schema:problem-brief:1.0",
      cardinality: "ONE",
      allow_partial: false,
    },
    routing_metadata: baseRoutingMetadata(),
    provenance: {
      source_stage: "SYNTHESIZE",
      parent_packet_id: parentId,
      input_artifact_refs: ["artifact://engineering_report/latest"],
      decision_ref: null,
    },
  }
}

/**
 * Map mock/general structured_output → solve_mechanics_request_v1.
 * Strict: missing fields → throws (caller sets harness_error / REWORK).
 */
export function mapStructuredBriefToSolveRequest(so: Record<string, unknown>): Record<string, unknown> {
  const block = so.block_material_id
  const surface = so.surface_material_id
  const fN = so.applied_force_N
  const side = so.cube_side_m
  if (typeof block !== "string" || typeof surface !== "string") {
    throw new Error("brief missing block_material_id or surface_material_id")
  }
  if (typeof fN !== "number" || typeof side !== "number") {
    throw new Error("brief missing applied_force_N or cube_side_m as numbers")
  }
  if (side <= 0) {
    throw new Error("cube_side_m must be > 0")
  }
  const mappingAssumptions: string[] = []
  const disp = so.displacement_m
  const displacement_m =
    typeof disp === "number" && disp > 0 ? disp : (() => {
      mappingAssumptions.push("defaulted displacement_m=1.0")
      return 1.0
    })()
  return {
    schema_version: "1.0.0",
    assumption_profile_id: "RIGID_BLOCK_DRY_SLIDING_V1",
    assumption_overrides: { fluid_id: null, viscous_enabled: false },
    geometry: { shape: "CUBE", cube_side_m: side },
    block_material_id: block,
    surface_material_id: surface,
    fluid_id: null,
    applied_force_N: fN,
    force_direction_assumption: "horizontal_in_plane",
    displacement_m,
    assumptions: mappingAssumptions,
  }
}

export function createPhysicsHarnessWorkflow(cfg: PlatformConfig) {
  async function intakeNode(
    state: PhysicsHarnessState,
  ): Promise<Partial<PhysicsHarnessState>> {
    if (!cfg.modelRuntimeBaseUrl) {
      return {
        harness_error: "MODEL_RUNTIME_URL unset",
        current_step: "failed",
      }
    }
    const rootId = randomUUID()
    const pkt = buildIntakePacket(rootId, state.user_prompt)
    try {
      const inf = await postInferGeneral(cfg, pkt, true)
      return {
        root_packet_id: rootId,
        intake_infer: inf as unknown as Record<string, unknown>,
        current_step: "map",
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      return { harness_error: msg, current_step: "failed" }
    }
  }

  function mapNode(state: PhysicsHarnessState): Partial<PhysicsHarnessState> {
    const inf = state.intake_infer as ModelRuntimeInferResponseShape | undefined
    const so = inf?.structured_output
    if (!so || typeof so !== "object") {
      return {
        harness_error: "INTAKE missing structured_output",
        current_step: "failed",
      }
    }
    try {
      const sr = mapStructuredBriefToSolveRequest(so as Record<string, unknown>)
      return { solve_request: sr, current_step: "solve" }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      return { harness_error: `BRIEF_MAPPING: ${msg}`, current_step: "failed" }
    }
  }

  async function solveNode(
    state: PhysicsHarnessState,
  ): Promise<Partial<PhysicsHarnessState>> {
    try {
      const rep = await postSolveMechanics(cfg, state.solve_request ?? {})
      return { engineering_report: rep, current_step: "verify" }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      return { harness_error: msg, current_step: "failed" }
    }
  }

  async function verifyNode(
    state: PhysicsHarnessState,
  ): Promise<Partial<PhysicsHarnessState>> {
    try {
      const vo = await postSolveVerify(cfg, state.engineering_report ?? {})
      return { verification_outcome: vo, current_step: "synthesize" }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      return { harness_error: msg, current_step: "failed" }
    }
  }

  async function synthesizeNode(
    state: PhysicsHarnessState,
  ): Promise<Partial<PhysicsHarnessState>> {
    const vo = state.verification_outcome
    if (vo?.status !== "PASS") {
      return {
        harness_error: `verification status ${String(vo?.status)}`,
        current_step: "failed",
      }
    }
    const root = state.root_packet_id
    if (!root) {
      return { harness_error: "missing root_packet_id", current_step: "failed" }
    }
    const pkt = buildSynthesizePacket(root, state.user_prompt)
    try {
      const inf = await postInferGeneral(cfg, pkt, false)
      const strict =
        (process.env.SYNTHESIS_STRICT_GROUNDING ?? "").toLowerCase() in
        { "1": true, "true": true, "yes": true }
      if (strict) {
        const text = String((inf as { text?: unknown }).text ?? "")
        assertSynthesisGrounded(state.engineering_report ?? {}, text)
      }
      return {
        synthesis_infer: inf as unknown as Record<string, unknown>,
        current_step: "complete",
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      return { harness_error: msg, current_step: "failed" }
    }
  }

  function routeAfterIntake(s: PhysicsHarnessState): "map" | "end" {
    if (s.harness_error || s.current_step === "failed") {
      return "end"
    }
    return "map"
  }
  function routeAfterMap(s: PhysicsHarnessState): "solve" | "end" {
    if (s.harness_error || s.current_step === "failed") {
      return "end"
    }
    return "solve"
  }
  function routeAfterSolve(s: PhysicsHarnessState): "verify" | "end" {
    if (s.harness_error || s.current_step === "failed") {
      return "end"
    }
    return "verify"
  }
  function routeAfterVerify(s: PhysicsHarnessState): "synthesize" | "end" {
    if (s.harness_error || s.current_step === "failed") {
      return "end"
    }
    return "synthesize"
  }

  const graph = new StateGraph(PhysicsHarnessAnnotation)
    .addNode("intake", intakeNode)
    .addNode("map", mapNode)
    .addNode("solve", solveNode)
    .addNode("verify", verifyNode)
    .addNode("synthesize", synthesizeNode)
    .addEdge(START, "intake")
    .addConditionalEdges("intake", routeAfterIntake, { map: "map", end: END })
    .addConditionalEdges("map", routeAfterMap, { solve: "solve", end: END })
    .addConditionalEdges("solve", routeAfterSolve, { verify: "verify", end: END })
    .addConditionalEdges("verify", routeAfterVerify, {
      synthesize: "synthesize",
      end: END,
    })
    .addEdge("synthesize", END)

  return graph.compile()
}

/** Narrow shape for map node (avoid importing client types circularly). */
type ModelRuntimeInferResponseShape = {
  structured_output?: Record<string, unknown>
}

function assertSynthesisGrounded(report: Record<string, unknown>, text: string): void {
  const allowedNums = collectNumericValues(report)
  // Avoid treating exponent digits in unit strings (e.g. m/s^2) as numeric claims.
  const textForNums = text.replace(/m\/s\^2/g, "").replace(/mps2/g, "")
  const numbers = textForNums.match(/-?\d+(?:\.\d+)?/g) ?? []
  for (const tok of numbers) {
    const n = Number(tok)
    if (!Number.isFinite(n)) {
      continue
    }
    const ok = allowedNums.some((v) => nearlyEqual(v, n))
    if (!ok) {
      throw new Error(`SYNTHESIS introduced number not in report: ${tok}`)
    }
  }

  const allowedUnits = collectAllowedUnits(report)
  const units = extractUnitTokens(text)
  for (const u of units) {
    if (!allowedUnits.has(u)) {
      throw new Error(`SYNTHESIS introduced unit not in report: ${u}`)
    }
  }
}

function nearlyEqual(a: number, b: number): boolean {
  const diff = Math.abs(a - b)
  const scale = Math.max(1, Math.abs(a), Math.abs(b))
  return diff <= 1e-9 * scale
}

function collectNumericValues(obj: unknown): number[] {
  const out: number[] = []
  const stack: unknown[] = [obj]
  while (stack.length > 0) {
    const v = stack.pop()
    if (typeof v === "number" && Number.isFinite(v)) {
      out.push(v)
      continue
    }
    if (Array.isArray(v)) {
      for (const it of v) stack.push(it)
      continue
    }
    if (v && typeof v === "object") {
      for (const it of Object.values(v as Record<string, unknown>)) stack.push(it)
    }
  }
  return out
}

function collectAllowedUnits(report: Record<string, unknown>): Set<string> {
  const allowed = new Set<string>()
  const json = JSON.stringify(report)
  if (json.includes("_N")) allowed.add("N")
  if (json.includes("_J")) allowed.add("J")
  if (json.includes("_mps2")) {
    allowed.add("m/s^2")
    allowed.add("mps2")
  }
  if (json.includes("_kg")) allowed.add("kg")
  if (json.includes("_m")) allowed.add("m")
  return allowed
}

function extractUnitTokens(text: string): string[] {
  const units: string[] = []
  // Common physics units (keep small and explicit; expand only with spec)
  const rx = /\b(m\/s\^2|mps2|Pa|N|J|kg|m)\b/g
  let m: RegExpExecArray | null
  while ((m = rx.exec(text)) !== null) {
    units.push(m[1] ?? m[0])
  }
  return units
}
