import { spawnSync } from "node:child_process"
import { chmod, mkdtemp, mkdir, rm, writeFile } from "node:fs/promises"
import os from "node:os"
import path from "node:path"
import { describe, expect, it, vi } from "vitest"
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

  it("POST /v1/agents/run preserves the direct-agent envelope through OrchestrationEngine", async () => {
    process.env.LLM_BACKEND = "mock"
    const app = buildServer()
    const res = await app.inject({
      method: "POST",
      url: "/v1/agents/run",
      payload: {
        agent: {
          name: "researcher",
          model: "mock-model",
          systemPrompt: "You are a researcher.",
        },
        prompt: "Summarize the current task.",
      },
    })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.body) as {
      success: boolean
      output: string
      tokenUsage: { input_tokens: number; output_tokens: number }
      toolCalls: unknown[]
    }
    expect(body.success).toBe(true)
    expect(body.output).toContain("Echo")
    expect(typeof body.tokenUsage.input_tokens).toBe("number")
    expect(typeof body.tokenUsage.output_tokens).toBe("number")
    expect(Array.isArray(body.toolCalls)).toBe(true)
  })

  it("GET /v1/workflows lists workflows", async () => {
    const app = buildServer()
    const res = await app.inject({ method: "GET", url: "/v1/workflows" })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.body) as { workflows: string[] }
    expect(body.workflows).toContain("wrkhrs_chat")
    expect(body.workflows).not.toContain("engineering_physics_v1")
  })

  it("POST /v1/teams/run preserves the team envelope through OrchestrationEngine", async () => {
    process.env.LLM_BACKEND = "mock"
    const app = buildServer()
    const res = await app.inject({
      method: "POST",
      url: "/v1/teams/run",
      payload: {
        team: {
          name: "research-team",
          agents: [
            {
              name: "planner",
              model: "mock-model",
              systemPrompt: "You plan work.",
            },
            {
              name: "writer",
              model: "mock-model",
              systemPrompt: "You write summaries.",
            },
          ],
        },
        goal: "Produce a short status update.",
      },
    })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.body) as {
      success: boolean
      totalTokenUsage: { input_tokens: number; output_tokens: number }
      agentResults: Record<string, { output: string }>
    }
    expect(body.success).toBe(true)
    expect(typeof body.totalTokenUsage.input_tokens).toBe("number")
    expect(typeof body.totalTokenUsage.output_tokens).toBe("number")
    expect(body.agentResults.planner?.output).toContain("Echo")
    expect(body.agentResults.writer?.output).toContain("Echo")
  })

  it("POST /v1/tasks/run preserves the task envelope through OrchestrationEngine", async () => {
    process.env.LLM_BACKEND = "mock"
    const app = buildServer()
    const res = await app.inject({
      method: "POST",
      url: "/v1/tasks/run",
      payload: {
        team: {
          name: "task-team",
          agents: [
            {
              name: "executor",
              model: "mock-model",
              systemPrompt: "You execute assigned tasks.",
            },
          ],
        },
        tasks: [
          {
            title: "Inspect state",
            description: "Inspect the current task state and summarize it.",
            assignee: "executor",
          },
        ],
      },
    })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.body) as {
      success: boolean
      totalTokenUsage: { input_tokens: number; output_tokens: number }
      agentResults: Record<string, { output: string }>
    }
    expect(body.success).toBe(true)
    expect(typeof body.totalTokenUsage.input_tokens).toBe("number")
    expect(typeof body.totalTokenUsage.output_tokens).toBe("number")
    expect(body.agentResults.executor?.output).toContain("Echo")
  })

  it("legacy engineering_physics_v1 workflow returns 410", async () => {
    const app = buildServer()
    const res = await app.inject({
      method: "POST",
      url: "/v1/workflows/execute",
      payload: {
        workflow_name: "engineering_physics_v1",
        input_data: { user_prompt: "Sliding steel cube" },
      },
    })
    expect(res.statusCode).toBe(410)
    const body = JSON.parse(res.body) as { detail: string }
    expect(body.detail).toContain("archived")
    expect(body.detail).toContain("server-local-archive")
  })

  it("legacy engineering_physics_v1 schema returns 410", async () => {
    const app = buildServer()
    const res = await app.inject({
      method: "GET",
      url: "/v1/workflows/engineering_physics_v1/schema",
    })
    expect(res.statusCode).toBe(410)
    const body = JSON.parse(res.body) as { detail: string }
    expect(body.detail).toContain("archived")
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

  it("POST /v1/workflows/execute engineering_workflow bridges to clarification without task_packet", async () => {
    process.env.LLM_BACKEND = "mock"
    process.env.ORCHESTRATOR_API_URL = "http://127.0.0.1:7777"
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string | URL) => {
        const u = typeof url === "string" ? url : url.toString()
        if (u.includes("/api/control-plane/engineering/intake")) {
          return new Response(
            JSON.stringify({
              ok: true,
              status: "CLARIFICATION_REQUIRED",
              engineering_session_id: "sess-1",
              problem_brief: { title: "Draft" },
              problem_brief_ref: "artifact://problem_brief/draft-1",
              clarification_questions: ["What system is in scope?"],
            }),
            { status: 200 },
          )
        }
        return new Response("nf", { status: 404 })
      }),
    )

    const app = buildServer()
    const res = await app.inject({
      method: "POST",
      url: "/v1/workflows/execute",
      payload: {
        workflow_name: "engineering_workflow",
        input_data: {
          messages: [
            {
              role: "user",
              content:
                "Design an engineering workflow that refactors multiple files and adds deterministic verification gates.",
            },
          ],
        },
      },
    })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.body) as {
      status: string
      result: { final_response?: string; referential_state?: { engineering_session_id?: string } }
    }
    expect(body.status).toBe("completed")
    expect(body.result?.final_response).toContain("Engineering clarification required")
    expect(body.result?.referential_state?.engineering_session_id).toBe("sess-1")
    vi.unstubAllGlobals()
    delete process.env.ORCHESTRATOR_API_URL
  })

  it("POST /v1/workflows/execute engineering_workflow dispatches coding_model packets via Claw Code", async () => {
    process.env.LLM_BACKEND = "mock"
    process.env.ORCHESTRATOR_API_URL = "http://127.0.0.1:7777"
    const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), "agent-platform-claw-workflow-"))
    const fakeClaw = await createFakeClawBinary("generated governed patch")
    process.env.CLAW_CODE_BINARY = fakeClaw
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string | URL) => {
        const u = typeof url === "string" ? url : url.toString()
        if (u.includes("/api/control-plane/engineering/intake")) {
          return new Response(
            JSON.stringify({
              ok: true,
              status: "READY",
              engineering_session_id: "sess-2",
              problem_brief: { problem_brief_id: "pb-1", title: "Strict task" },
              problem_brief_ref: "artifact://problem_brief/pb-1",
              knowledge_pool_assessment: {
                knowledge_pool_assessment_id: "kpa-1",
                schema_version: "1.0.0",
                coverage_class: "strong",
                required_for_mode: true,
                candidate_pack_refs: ["artifact://knowledge-pack/demo-pack"],
              },
              knowledge_pool_assessment_ref: "artifact://knowledge_pool_assessment/kpa-1",
              knowledge_pool_coverage: "strong",
              knowledge_candidate_refs: ["artifact://knowledge-pack/demo-pack"],
              response_mode: "engineering",
              response_control_ref: "artifact://response-control-assessment/rca-1",
              selected_knowledge_pool_refs: ["artifact://knowledge-pool/computational_engineering"],
              selected_module_refs: ["artifact://module-card/engineering_orchestration_stack"],
              selected_technique_refs: [
                "artifact://technique-card/artifact_first_task_graph_execution",
              ],
              selected_theory_refs: [
                "artifact://theory-card/computational_engineering_numerical_methods",
              ],
              knowledge_role_contexts: {
                coder: {
                  role_context_bundle_id: "coder_ctx_1",
                  role: "coder",
                  source_artifact_refs: ["artifact://knowledge-pack/demo-pack"],
                  compiled_summary: "Use the verified demo pack and runtime.",
                },
              },
              knowledge_role_context_refs: ["artifact://role_context_bundle/coder_ctx_1"],
              knowledge_required: true,
              engineering_state: {
                engineering_state_id: "es-1",
                open_issues: [],
                conflicts: [],
              },
              engineering_state_ref: "artifact://engineering_state/es-1",
              task_queue: { task_queue_id: "queue-1", items: [] },
              task_packets: [
                {
                  task_packet_id: "11111111-1111-4111-8111-111111111111",
                  task_type: "CODEGEN",
                  objective: "Implement the governed patch",
                  input_artifact_refs: [
                    "artifact://problem_brief/pb-1",
                    "artifact://engineering_state/es-1",
                  ],
                  required_outputs: [{ artifact_type: "CODE_PATCH" }],
                  acceptance_criteria: ["Emit a patch artifact"],
                  constraints: ["Honor the governed packet"],
                  response_control_ref: "artifact://response-control-assessment/rca-1",
                  selected_knowledge_pool_refs: [
                    "artifact://knowledge-pool/computational_engineering",
                  ],
                  selected_module_refs: [
                    "artifact://module-card/engineering_orchestration_stack",
                  ],
                  selected_technique_refs: [
                    "artifact://technique-card/artifact_first_task_graph_execution",
                  ],
                  selected_theory_refs: [
                    "artifact://theory-card/computational_engineering_numerical_methods",
                  ],
                  routing_metadata: { selected_executor: "coding_model" },
                  budget_policy: { allow_escalation: false },
                },
                {
                  task_packet_id: "22222222-2222-4222-8222-222222222222",
                  task_type: "VALIDATION",
                  input_artifact_refs: [
                    "artifact://problem_brief/pb-1",
                    "artifact://engineering_state/es-1",
                  ],
                  required_outputs: [{ artifact_type: "VERIFICATION_REPORT" }],
                  acceptance_criteria: ["Verification report emitted"],
                  validation_requirements: ["criterion_1:test:target 1 pass"],
                  response_control_ref: "artifact://response-control-assessment/rca-1",
                  selected_knowledge_pool_refs: [
                    "artifact://knowledge-pool/computational_engineering",
                  ],
                  selected_module_refs: [
                    "artifact://module-card/engineering_orchestration_stack",
                  ],
                  selected_technique_refs: [
                    "artifact://technique-card/artifact_first_task_graph_execution",
                  ],
                  selected_theory_refs: [
                    "artifact://theory-card/computational_engineering_numerical_methods",
                  ],
                  routing_metadata: { selected_executor: "deterministic_validator" },
                  budget_policy: { allow_escalation: true },
                },
              ],
              ready_for_task_decomposition: true,
              required_gates: [],
              clarification_questions: [],
            }),
            { status: 200 },
          )
        }
        return new Response("nf", { status: 404 })
      }),
    )

    const app = buildServer()
    const res = await app.inject({
      method: "POST",
      url: "/v1/workflows/execute",
      payload: {
        workflow_name: "engineering_workflow",
        input_data: {
          engagement_mode: "strict_engineering",
          engagement_mode_source: "explicit",
          minimum_engagement_mode: "strict_engineering",
          context: {
            workspace: {
              worktree_path: workspaceRoot,
            },
          },
          messages: [
            {
              role: "user",
              content: "Implement the governed patch for the strict engineering workflow.",
            },
          ],
        },
      },
    })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.body) as {
      status: string
      result: {
        final_response?: string
        verification_outcome?: string
        engagement_mode?: string
        ready_for_task_decomposition?: boolean
        referential_state?: { active_task_packet_ref?: string; selected_executor?: string }
      }
    }
    expect(body.status).toBe("completed")
    expect(body.result?.final_response).toContain("generated governed patch")
    expect(body.result?.verification_outcome).toBe("PASS")
    expect(body.result?.engagement_mode).toBe("strict_engineering")
    expect(body.result?.ready_for_task_decomposition).toBe(true)
    expect(body.result?.referential_state?.active_task_packet_ref).toBe(
      "artifact://task_packet/11111111-1111-4111-8111-111111111111",
    )
    expect(body.result?.referential_state?.selected_executor).toBe("coding_model")
    vi.unstubAllGlobals()
    delete process.env.ORCHESTRATOR_API_URL
    delete process.env.CLAW_CODE_BINARY
    await rm(workspaceRoot, { recursive: true, force: true })
    await rm(path.dirname(fakeClaw), { recursive: true, force: true })
  })

  it("POST /v1/workflows/execute engineering_workflow blocks when required theory refs are missing", async () => {
    process.env.LLM_BACKEND = "mock"
    process.env.ORCHESTRATOR_API_URL = "http://127.0.0.1:7777"
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string | URL) => {
        const u = typeof url === "string" ? url : url.toString()
        if (u.includes("/api/control-plane/engineering/intake")) {
          return new Response(
            JSON.stringify({
              ok: true,
              status: "READY",
              engineering_session_id: "sess-knowledge-blocked",
              problem_brief: { problem_brief_id: "pb-1", title: "Strict task" },
              problem_brief_ref: "artifact://problem_brief/pb-1",
              knowledge_pool_assessment_ref: "artifact://knowledge_pool_assessment/kpa-1",
              knowledge_pool_coverage: "strong",
              knowledge_candidate_refs: ["artifact://knowledge-pack/demo-pack"],
              knowledge_required: true,
              response_mode: "engineering",
              response_control_ref: "artifact://response-control-assessment/rca-1",
              selected_knowledge_pool_refs: ["artifact://knowledge-pool/computational_engineering"],
              selected_module_refs: ["artifact://module-card/engineering_orchestration_stack"],
              selected_technique_refs: [
                "artifact://technique-card/artifact_first_task_graph_execution",
              ],
              selected_theory_refs: [],
              engineering_state: {
                engineering_state_id: "es-1",
                open_issues: [],
                conflicts: [],
              },
              engineering_state_ref: "artifact://engineering_state/es-1",
              task_queue: { task_queue_id: "queue-1", items: [] },
              task_packets: [
                {
                  task_packet_id: "55555555-5555-4555-8555-555555555555",
                  task_type: "CODEGEN",
                  objective: "Implement the governed patch",
                  input_artifact_refs: [
                    "artifact://problem_brief/pb-1",
                    "artifact://engineering_state/es-1",
                  ],
                  required_outputs: [{ artifact_type: "CODE_PATCH" }],
                  acceptance_criteria: ["Emit a patch artifact"],
                  constraints: ["Honor the governed packet"],
                  response_control_ref: "artifact://response-control-assessment/rca-1",
                  selected_knowledge_pool_refs: [
                    "artifact://knowledge-pool/computational_engineering",
                  ],
                  selected_module_refs: [
                    "artifact://module-card/engineering_orchestration_stack",
                  ],
                  selected_technique_refs: [
                    "artifact://technique-card/artifact_first_task_graph_execution",
                  ],
                  selected_theory_refs: [],
                  routing_metadata: { selected_executor: "coding_model" },
                  budget_policy: { allow_escalation: false },
                },
              ],
              ready_for_task_decomposition: true,
              required_gates: [],
              clarification_questions: [],
            }),
            { status: 200 },
          )
        }
        return new Response("nf", { status: 404 })
      }),
    )

    const app = buildServer()
    const res = await app.inject({
      method: "POST",
      url: "/v1/workflows/execute",
      payload: {
        workflow_name: "engineering_workflow",
        input_data: {
          messages: [
            {
              role: "user",
              content: "Implement the governed patch with missing theory refs.",
            },
          ],
        },
      },
    })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.body) as {
      status: string
      result: { final_response?: string; verification_outcome?: string; lifecycle_reason?: string }
    }
    expect(body.status).toBe("completed")
    expect(body.result?.final_response).toContain("selected_theory_refs")
    expect(body.result?.verification_outcome).toBe("BLOCKED")
    expect(body.result?.lifecycle_reason).toBe("governance_gate")
    vi.unstubAllGlobals()
    delete process.env.ORCHESTRATOR_API_URL
  })

  it("POST /v1/workflows/execute engineering_workflow fails closed when coding_model is unavailable", async () => {
    process.env.LLM_BACKEND = "mock"
    process.env.ORCHESTRATOR_API_URL = "http://127.0.0.1:7777"
    delete process.env.CLAW_CODE_BINARY
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string | URL) => {
        const u = typeof url === "string" ? url : url.toString()
        if (u.includes("/api/control-plane/engineering/intake")) {
          return new Response(
            JSON.stringify({
              ok: true,
              status: "READY",
              engineering_session_id: "sess-3",
              problem_brief: { problem_brief_id: "pb-1", title: "Strict task" },
              problem_brief_ref: "artifact://problem_brief/pb-1",
              response_mode: "engineering",
              response_control_ref: "artifact://response-control-assessment/rca-1",
              selected_knowledge_pool_refs: ["artifact://knowledge-pool/computational_engineering"],
              selected_module_refs: ["artifact://module-card/engineering_orchestration_stack"],
              selected_technique_refs: [
                "artifact://technique-card/artifact_first_task_graph_execution",
              ],
              selected_theory_refs: [
                "artifact://theory-card/computational_engineering_numerical_methods",
              ],
              engineering_state: {
                engineering_state_id: "es-1",
                open_issues: [],
                conflicts: [],
              },
              engineering_state_ref: "artifact://engineering_state/es-1",
              task_queue: { task_queue_id: "queue-1", items: [] },
              task_packets: [
                {
                  task_packet_id: "11111111-1111-4111-8111-111111111111",
                  task_type: "CODEGEN",
                  objective: "Implement the governed patch",
                  input_artifact_refs: [
                    "artifact://problem_brief/pb-1",
                    "artifact://engineering_state/es-1",
                  ],
                  required_outputs: [{ artifact_type: "CODE_PATCH" }],
                  acceptance_criteria: ["Emit a patch artifact"],
                  constraints: ["Honor the governed packet"],
                  response_control_ref: "artifact://response-control-assessment/rca-1",
                  selected_knowledge_pool_refs: [
                    "artifact://knowledge-pool/computational_engineering",
                  ],
                  selected_module_refs: [
                    "artifact://module-card/engineering_orchestration_stack",
                  ],
                  selected_technique_refs: [
                    "artifact://technique-card/artifact_first_task_graph_execution",
                  ],
                  selected_theory_refs: [
                    "artifact://theory-card/computational_engineering_numerical_methods",
                  ],
                  routing_metadata: { selected_executor: "coding_model" },
                  budget_policy: { allow_escalation: false },
                },
                {
                  task_packet_id: "22222222-2222-4222-8222-222222222222",
                  task_type: "VALIDATION",
                  input_artifact_refs: [
                    "artifact://problem_brief/pb-1",
                    "artifact://engineering_state/es-1",
                  ],
                  required_outputs: [{ artifact_type: "VERIFICATION_REPORT" }],
                  acceptance_criteria: ["Verification report emitted"],
                  validation_requirements: ["criterion_1:test:target 1 pass"],
                  response_control_ref: "artifact://response-control-assessment/rca-1",
                  selected_knowledge_pool_refs: [
                    "artifact://knowledge-pool/computational_engineering",
                  ],
                  selected_module_refs: [
                    "artifact://module-card/engineering_orchestration_stack",
                  ],
                  selected_technique_refs: [
                    "artifact://technique-card/artifact_first_task_graph_execution",
                  ],
                  selected_theory_refs: [
                    "artifact://theory-card/computational_engineering_numerical_methods",
                  ],
                  routing_metadata: { selected_executor: "deterministic_validator" },
                  budget_policy: { allow_escalation: true },
                },
              ],
              ready_for_task_decomposition: true,
              required_gates: [],
              clarification_questions: [],
            }),
            { status: 200 },
          )
        }
        return new Response("nf", { status: 404 })
      }),
    )

    const app = buildServer()
    const res = await app.inject({
      method: "POST",
      url: "/v1/workflows/execute",
      payload: {
        workflow_name: "engineering_workflow",
        input_data: {
          messages: [
            {
              role: "user",
              content: "Implement the governed patch for the strict engineering workflow.",
            },
          ],
        },
      },
    })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.body) as {
      status: string
      result: { final_response?: string; verification_outcome?: string; lifecycle_reason?: string }
    }
    expect(body.status).toBe("completed")
    expect(body.result?.final_response).toContain("requires a governed workspaceRoot")
    expect(body.result?.verification_outcome).toBe("BLOCKED")
    expect(body.result?.lifecycle_reason).toBe("executor_unavailable")
    vi.unstubAllGlobals()
    delete process.env.ORCHESTRATOR_API_URL
  })

  it("POST /v1/workflows/execute engineering_workflow blocks strategic_reviewer before typed escalation", async () => {
    process.env.LLM_BACKEND = "mock"
    process.env.ORCHESTRATOR_API_URL = "http://127.0.0.1:7777"
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string | URL) => {
        const u = typeof url === "string" ? url : url.toString()
        if (u.includes("/api/control-plane/engineering/intake")) {
          return new Response(
            JSON.stringify({
              ok: true,
              status: "READY",
              engineering_session_id: "sess-4",
              problem_brief: { problem_brief_id: "pb-1", title: "Strict task" },
              problem_brief_ref: "artifact://problem_brief/pb-1",
              engineering_state: {
                engineering_state_id: "es-1",
                open_issues: [],
                conflicts: [],
              },
              engineering_state_ref: "artifact://engineering_state/es-1",
              task_queue: { task_queue_id: "queue-1", items: [] },
              task_packets: [
                {
                  task_packet_id: "33333333-3333-4333-8333-333333333333",
                  task_type: "REVIEW",
                  objective: "Review the governed execution decision",
                  input_artifact_refs: [
                    "artifact://problem_brief/pb-1",
                    "artifact://engineering_state/es-1",
                  ],
                  required_outputs: [{ artifact_type: "DECISION_LOG" }],
                  acceptance_criteria: ["Emit a strategic review note"],
                  constraints: ["Only run after typed escalation"],
                  routing_metadata: { selected_executor: "strategic_reviewer" },
                  budget_policy: { allow_escalation: true },
                },
              ],
              ready_for_task_decomposition: true,
              required_gates: [],
              clarification_questions: [],
            }),
            { status: 200 },
          )
        }
        return new Response("nf", { status: 404 })
      }),
    )

    const app = buildServer()
    const res = await app.inject({
      method: "POST",
      url: "/v1/workflows/execute",
      payload: {
        workflow_name: "engineering_workflow",
        input_data: {
          messages: [
            {
              role: "user",
              content: "Request strategic review before any typed escalation exists.",
            },
          ],
        },
      },
    })
    expect(res.statusCode).toBe(200)
    const body = JSON.parse(res.body) as {
      status: string
      result: { final_response?: string; verification_outcome?: string; lifecycle_reason?: string }
    }
    expect(body.status).toBe("completed")
    expect(body.result?.final_response).toContain(
      "strategic_reviewer may only run after typed escalation",
    )
    expect(body.result?.verification_outcome).toBe("BLOCKED")
    expect(body.result?.lifecycle_reason).toBe("awaiting_strategic_review")
    vi.unstubAllGlobals()
    delete process.env.ORCHESTRATOR_API_URL
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

async function createFakeClawBinary(outputText: string): Promise<string> {
  const root = await mkdtemp(path.join(os.tmpdir(), "fake-claw-"))
  const scriptPath = path.join(root, "claw")
  const script = `#!/usr/bin/env node
const fs = require("node:fs");
const path = require("node:path");
const outputText = process.env.CLAW_TEST_OUTPUT_TEXT || ${JSON.stringify(outputText)};

function send(message) {
  const payload = Buffer.from(JSON.stringify(message), "utf8");
  process.stdout.write(Buffer.from("Content-Length: " + payload.length + "\\r\\n\\r\\n", "utf8"));
  process.stdout.write(payload);
}

function toolResult(id, payload) {
  send({
    jsonrpc: "2.0",
    id,
    result: {
      content: [{ type: "text", text: JSON.stringify(payload) }],
    },
  });
}

function writeWorkerState(cwd, state) {
  const stateDir = path.join(cwd, ".claw");
  fs.mkdirSync(stateDir, { recursive: true });
  fs.writeFileSync(path.join(stateDir, "worker-state.json"), JSON.stringify(state, null, 2));
}

function parseFrames(chunkBuffer) {
  const messages = [];
  while (true) {
    const headerEnd = chunkBuffer.indexOf("\\r\\n\\r\\n");
    if (headerEnd === -1) break;
    const header = chunkBuffer.slice(0, headerEnd).toString("utf8");
    const match = header.match(/content-length:\\s*(\\d+)/i);
    if (!match) break;
    const length = Number(match[1]);
    const frameStart = headerEnd + 4;
    const frameEnd = frameStart + length;
    if (chunkBuffer.length < frameEnd) break;
    messages.push(JSON.parse(chunkBuffer.slice(frameStart, frameEnd).toString("utf8")));
    chunkBuffer = chunkBuffer.slice(frameEnd);
  }
  return { messages, rest: chunkBuffer };
}

if (process.argv[2] !== "mcp" || process.argv[3] !== "serve") {
  process.exit(0);
}

let buffer = Buffer.alloc(0);
process.stdin.on("data", (chunk) => {
  buffer = Buffer.concat([buffer, chunk]);
  const parsed = parseFrames(buffer);
  buffer = parsed.rest;
  for (const message of parsed.messages) {
    if (message.method === "initialize") {
      send({
        jsonrpc: "2.0",
        id: message.id,
        result: {
          protocolVersion: message.params.protocolVersion,
          capabilities: {},
          serverInfo: { name: "fake-claw", version: "0.1.0" },
        },
      });
      continue;
    }
    if (message.method === "tools/list") {
      send({
        jsonrpc: "2.0",
        id: message.id,
        result: {
          tools: [
            { name: "RunTaskPacket" },
            { name: "WorkerCreate" },
            { name: "WorkerObserve" },
            { name: "WorkerResolveTrust" },
            { name: "WorkerRestart" },
            { name: "Agent" },
          ],
        },
      });
      continue;
    }
    if (message.method !== "tools/call") {
      continue;
    }
    const name = message.params.name;
    const args = message.params.arguments || {};
    if (name === "RunTaskPacket") {
      toolResult(message.id, { task_id: "task-1", status: "created" });
      continue;
    }
    if (name === "WorkerCreate") {
      writeWorkerState(args.cwd, {
        worker_id: "worker-1",
        status: "spawning",
        is_ready: false,
        trust_gate_cleared: true,
        seconds_since_update: 0,
      });
      toolResult(message.id, { worker_id: "worker-1", trust_auto_resolve: true });
      continue;
    }
    if (name === "WorkerObserve") {
      writeWorkerState(process.cwd(), {
        worker_id: "worker-1",
        status: "ready_for_prompt",
        is_ready: true,
        trust_gate_cleared: true,
        seconds_since_update: 0,
      });
      toolResult(message.id, { worker_id: "worker-1", status: "ready_for_prompt" });
      continue;
    }
    if (name === "WorkerResolveTrust" || name === "WorkerRestart") {
      toolResult(message.id, { worker_id: "worker-1", status: "spawning" });
      continue;
    }
    if (name === "Agent") {
      const agentStore = process.env.CLAWD_AGENT_STORE || path.join(process.cwd(), ".clawd-agents");
      fs.mkdirSync(agentStore, { recursive: true });
      const manifestFile = path.join(agentStore, "agent-test.json");
      const outputFile = path.join(agentStore, "agent-test.md");
      const manifest = {
        agentId: "agent-test",
        status: "completed",
        manifestFile,
        outputFile,
      };
      fs.writeFileSync(outputFile, outputText);
      fs.writeFileSync(manifestFile, JSON.stringify(manifest, null, 2));
      toolResult(message.id, manifest);
    }
  }
});
`
  await writeFile(scriptPath, script, "utf8")
  await chmod(scriptPath, 0o755)
  return scriptPath
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
