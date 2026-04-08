import { spawnSync } from "node:child_process"
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises"
import os from "node:os"
import path from "node:path"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { buildServer } from "./server.js"

interface DevplaneRunSnapshot {
  status: string
  verification_results: Array<{ status: string }>
  artifacts: Array<{ path: string }>
}

describe("agent-platform server", () => {
  it("GET /health returns healthy", async () => {
    const app = buildServer()
    const res = await app.inject({ method: "GET", url: "/health" })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.body) as { status: string }
    expect(body.status).toBe("healthy")
  })

  it("POST /chat accepts messages", async () => {
    process.env.LLM_BACKEND = "mock"
    const app = buildServer()
    const res = await app.inject({
      method: "POST",
      url: "/chat",
      payload: {
        messages: [{ role: "user", content: "Hello world" }],
        model: "test",
      },
    })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.body) as {
      choices: Array<{ message: { content: string } }>
    }
    expect(body.choices[0]?.message.content).toContain("Echo")
  })

  it("GET /v1/workflows lists workflows", async () => {
    const app = buildServer()
    const res = await app.inject({ method: "GET", url: "/v1/workflows" })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.body) as { workflows: string[] }
    expect(body.workflows).toContain("wrkhrs_chat")
    expect(body.workflows).toContain("engineering_physics_v1")
  })

  describe("engineering_physics_v1", () => {
    beforeEach(() => {
      process.env.MODEL_RUNTIME_URL = "http://127.0.0.1:8765"
      vi.stubGlobal(
        "fetch",
        vi.fn(async (url: string | URL) => {
          const u = typeof url === "string" ? url : url.toString()
          if (u.includes("infer/general") && u.includes("workflow_root=true")) {
            return new Response(
              JSON.stringify({
                usage: { prompt_tokens: 1, completion_tokens: 1, latency_ms: 1 },
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
            const rep = {
              schema_version: "1.0.0",
              problem_brief: { summary: "t" },
              assumptions: ["a"],
              inputs: {},
              derived_quantities: {
                mass_kg: 7850,
                kinetic_friction_coefficient: 0.45,
                friction_force_N: 1,
              },
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
            return new Response(JSON.stringify(rep), { status: 200 })
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
          if (u.includes("workflow_root=false")) {
            return new Response(
              JSON.stringify({
                usage: { prompt_tokens: 1, completion_tokens: 1, latency_ms: 1 },
                model_id_resolved: "Qwen/Qwen3-4B",
                text: "Done.",
              }),
              { status: 200 },
            )
          }
          return new Response("nf", { status: 404 })
        }),
      )
    })
    afterEach(() => {
      vi.unstubAllGlobals()
      delete process.env.MODEL_RUNTIME_URL
    })

    it("POST /v1/workflows/execute completes with mocked model-runtime", async () => {
      process.env.LLM_BACKEND = "mock"
      const app = buildServer()
      const res = await app.inject({
        method: "POST",
        url: "/v1/workflows/execute",
        payload: {
          workflow_name: "engineering_physics_v1",
          input_data: { user_prompt: "Sliding steel cube" },
        },
      })
      expect(res.statusCode).toBe(200)
      const body = JSON.parse(res.body) as {
        status: string
        result: { verification_outcome?: { status: string }; final_response?: string }
      }
      expect(body.status).toBe("completed")
      expect(body.result?.verification_outcome?.status).toBe("PASS")
      expect(body.result?.final_response).toContain("Done")
    })
  })

  it("POST /v1/workflows/execute wrkhrs_chat returns completed + envelope", async () => {
    process.env.LLM_BACKEND = "mock"
    const app = buildServer()
    const res = await app.inject({
      method: "POST",
      url: "/v1/workflows/execute",
      payload: {
        workflow_name: "wrkhrs_chat",
        input_data: {
          messages: [{ role: "user", content: "what is gravity" }],
        },
      },
    })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.body) as {
      status: string
      workflow_name: string
      duration: number
      result: { final_response?: string }
    }
    expect(body.status).toBe("completed")
    expect(body.workflow_name).toBe("wrkhrs_chat")
    expect(typeof body.duration).toBe("number")
    expect(body.result?.final_response).toBeDefined()
  })

  it("GET /v1/workflows/:name/schema returns JSON", async () => {
    const app = buildServer()
    const res = await app.inject({
      method: "GET",
      url: "/v1/workflows/wrkhrs_chat/schema",
    })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.body) as { name: string }
    expect(body.name).toBe("wrkhrs_chat")
  })

  it("POST /v1/devplane/runs executes a mock internal run", async () => {
    process.env.LLM_BACKEND = "mock"
    const repo = await initGitRepo()
    const app = buildServer()
    const createRes = await app.inject({
      method: "POST",
      url: "/v1/devplane/runs",
      payload: {
        control_run_id: "control-run-1",
        task_id: "task-1",
        project_id: "proj-example",
        workspace: {
          canonical_repo_path: repo,
          worktree_path: repo,
          branch_name: "main",
          base_branch: "main",
          remote_name: "origin",
        },
        plan: {
          project_id: "proj-example",
          objective: "Inspect the repository and prepare for publish.",
          constraints: [],
          acceptance_criteria: ["Verification passes"],
          implementation_outline: ["Inspect repo"],
          verification_plan: ["git status --short"],
          delegation_hints: [],
          work_items: [],
          verification_blocks: [
            {
              name: "git_status",
              command: "git status --short",
              required: true,
            },
          ],
        },
        callback: {
          events_url: "http://127.0.0.1:9/api/dev/runs/1/events",
          complete_url: "http://127.0.0.1:9/api/dev/runs/1/complete",
        },
      },
    })
    expect(createRes.statusCode).toBe(200)
    const created = JSON.parse(createRes.body) as { run_id: string }

    let snapshot: DevplaneRunSnapshot | null = null
    for (let attempt = 0; attempt < 150; attempt += 1) {
      const statusRes = await app.inject({
        method: "GET",
        url: `/v1/devplane/runs/${created.run_id}`,
      })
      expect(statusRes.statusCode).toBe(200)
      snapshot = JSON.parse(statusRes.body) as DevplaneRunSnapshot
      if (
        snapshot &&
        ["ready_to_publish", "failed", "cancelled"].includes(snapshot.status)
      ) {
        break
      }
      await delay(20)
    }

    expect(snapshot?.status).toBe("ready_to_publish")
    expect(snapshot?.verification_results[0]?.status).toBe("passed")
    expect(snapshot?.artifacts.length).toBeGreaterThan(0)
    await rm(repo, { recursive: true, force: true })
  })
})

async function initGitRepo(): Promise<string> {
  const repo = await mkdtemp(path.join(os.tmpdir(), "agent-platform-devplane-"))
  await writeFile(path.join(repo, "README.md"), "# Example\n", "utf8")
  await mkdir(path.join(repo, "src"), { recursive: true })
  await writeFile(path.join(repo, "src", "index.ts"), "export const ok = true\n", "utf8")
  run(["git", "init", "-b", "main"], repo)
  run(["git", "config", "user.name", "Agent Platform Test"], repo)
  run(["git", "config", "user.email", "agent-platform@example.com"], repo)
  run(["git", "add", "."], repo)
  run(["git", "commit", "-m", "Initial commit"], repo)
  return repo
}

function run(command: string[], cwd: string): void {
  const result = spawnSync(command[0]!, command.slice(1), {
    cwd,
    encoding: "utf8",
    env: {
      ...process.env,
      // Tests should not depend on developer-global git config (e.g. commit signing helpers).
      GIT_CONFIG_GLOBAL: "/dev/null",
      GIT_CONFIG_SYSTEM: "/dev/null",
    },
  })
  if (result.status !== 0) {
    throw new Error(result.stderr || `Command failed: ${command.join(" ")}`)
  }
}

async function delay(ms: number): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, ms))
}
