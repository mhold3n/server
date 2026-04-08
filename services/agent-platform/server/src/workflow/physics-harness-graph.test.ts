import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { loadConfig } from "../config.js"
import {
  createPhysicsHarnessWorkflow,
  mapStructuredBriefToSolveRequest,
} from "./physics-harness-graph.js"

const sampleReport = {
  schema_version: "1.0.0",
  problem_brief: { summary: "test" },
  assumptions: ["a"],
  inputs: {},
  derived_quantities: { mass_kg: 7850, kinetic_friction_coefficient: 0.45, friction_force_N: 1 },
  results: {
    acceleration_mps2: 1,
    normal_force_N: 1,
    reaction_force_N: 1,
    resisting_force_N: 1,
    heat_dissipation_J: 1,
  },
  energy_balance: {
    work_in_J: 1,
    kinetic_energy_change_J: 0,
    dissipated_J: 1,
    residual_J: 0,
  },
  model_limits: [],
  comparison_case: {},
}

describe("physics harness graph", () => {
  beforeEach(() => {
    process.env.MODEL_RUNTIME_URL = "http://127.0.0.1:8765"
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string | URL) => {
        const u = typeof url === "string" ? url : url.toString()
        if (u.includes("infer/general") && u.includes("workflow_root=true")) {
          return new Response(
            JSON.stringify({
              usage: { prompt_tokens: 1, completion_tokens: 1, latency_ms: 0.5 },
              model_id_resolved: "Qwen/Qwen3-4B",
              structured_output: {
                block_material_id: "steel_7850",
                surface_material_id: "concrete_rough",
                applied_force_N: 40000,
                cube_side_m: 1.0,
              },
            }),
            { status: 200 },
          )
        }
        if (u.includes("solve/mechanics")) {
          return new Response(JSON.stringify(sampleReport), { status: 200 })
        }
        if (u.includes("solve/verify")) {
          return new Response(
            JSON.stringify({
              status: "PASS",
              checks: [],
              blocking_issues: [],
              tolerance_results: {},
            }),
            { status: 200 },
          )
        }
        if (u.includes("infer/general") && u.includes("workflow_root=false")) {
          return new Response(
            JSON.stringify({
              usage: { prompt_tokens: 1, completion_tokens: 2, latency_ms: 0.5 },
              model_id_resolved: "Qwen/Qwen3-4B",
              text: "Synthesis: block accelerates per verified report.",
            }),
            { status: 200 },
          )
        }
        return new Response("not found", { status: 404 })
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    delete process.env.MODEL_RUNTIME_URL
    delete process.env.SYNTHESIS_STRICT_GROUNDING
  })

  it("mapStructuredBriefToSolveRequest builds valid solve body", () => {
    const sr = mapStructuredBriefToSolveRequest({
      block_material_id: "steel_7850",
      surface_material_id: "concrete_rough",
      applied_force_N: 40000,
      cube_side_m: 1,
    })
    expect(sr.assumption_profile_id).toBe("RIGID_BLOCK_DRY_SLIDING_V1")
    expect(sr.block_material_id).toBe("steel_7850")
  })

  it("mapping assumption audit: defaulted displacement is recorded", () => {
    const sr = mapStructuredBriefToSolveRequest({
      block_material_id: "steel_7850",
      surface_material_id: "concrete_rough",
      applied_force_N: 40000,
      cube_side_m: 1,
    })
    expect(sr.displacement_m).toBe(1.0)
    const a = sr.assumptions as string[] | undefined
    expect(a).toContain("defaulted displacement_m=1.0")
  })

  it("invokes full harness with mocked fetch", async () => {
    const cfg = loadConfig()
    expect(cfg.modelRuntimeBaseUrl).toBe("http://127.0.0.1:8765")
    const g = createPhysicsHarnessWorkflow(cfg)
    const out = await g.invoke({
      user_prompt: "Steel cube sliding on concrete",
      current_step: "intake",
    })
    expect(out.harness_error).toBeUndefined()
    expect(out.verification_outcome?.status).toBe("PASS")
    const syn = out.synthesis_infer as { text?: string } | undefined
    expect(syn?.text).toContain("Synthesis")
  })

  it("synthesis no-new-units: strict grounding rejects units absent from report", async () => {
    process.env.SYNTHESIS_STRICT_GROUNDING = "1"
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string | URL) => {
        const u = typeof url === "string" ? url : url.toString()
        if (u.includes("infer/general") && u.includes("workflow_root=true")) {
          return new Response(
            JSON.stringify({
              usage: { prompt_tokens: 1, completion_tokens: 1, latency_ms: 0.5 },
              model_id_resolved: "Qwen/Qwen3-4B",
              structured_output: {
                block_material_id: "steel_7850",
                surface_material_id: "concrete_rough",
                applied_force_N: 40000,
                cube_side_m: 1.0,
              },
            }),
            { status: 200 },
          )
        }
        if (u.includes("solve/mechanics")) {
          return new Response(JSON.stringify(sampleReport), { status: 200 })
        }
        if (u.includes("solve/verify")) {
          return new Response(
            JSON.stringify({
              status: "PASS",
              checks: [],
              blocking_issues: [],
              tolerance_results: {},
            }),
            { status: 200 },
          )
        }
        if (u.includes("infer/general") && u.includes("workflow_root=false")) {
          // 'Pa' is not present in the report context; should be rejected.
          return new Response(
            JSON.stringify({
              usage: { prompt_tokens: 1, completion_tokens: 2, latency_ms: 0.5 },
              model_id_resolved: "Qwen/Qwen3-4B",
              text: "Acceleration is 1 m/s^2 and pressure is 1 Pa.",
            }),
            { status: 200 },
          )
        }
        return new Response("not found", { status: 404 })
      }),
    )
    const cfg = loadConfig()
    const g = createPhysicsHarnessWorkflow(cfg)
    const out = await g.invoke({
      user_prompt: "Steel cube sliding on concrete",
      current_step: "intake",
    })
    expect(out.harness_error).toContain("unit not in report")
  })
})
