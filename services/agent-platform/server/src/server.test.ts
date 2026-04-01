import { describe, expect, it } from "vitest"
import { buildServer } from "./server.js"

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
})
