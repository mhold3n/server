import test from "node:test"
import assert from "node:assert/strict"
import {
  createDevplaneClient,
  formatForText,
  summarizeStatus,
} from "../src/operator-client.js"

test("createDevplaneClient sends listProjects to /api/dev/projects", async () => {
  const calls = []
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, options })
    return {
      ok: true,
      status: 200,
      async text() {
        return "[]"
      },
    }
  }

  const client = createDevplaneClient({ baseUrl: "http://api:8080" })
  const result = await client.listProjects()
  assert.deepEqual(result, [])
  assert.equal(calls[0].url, "http://api:8080/api/dev/projects")
})

test("submitTask posts JSON payload to /api/dev/tasks", async () => {
  let seenBody = null
  globalThis.fetch = async (_url, options = {}) => {
    seenBody = options.body
    return {
      ok: true,
      status: 200,
      async text() {
        return JSON.stringify({ task_id: "task-1" })
      },
    }
  }

  const client = createDevplaneClient({ baseUrl: "http://api:8080" })
  const response = await client.submitTask({
    project_id: "proj-1",
    user_intent: "Implement feature",
  })
  assert.equal(response.task_id, "task-1")
  assert.match(String(seenBody), /"project_id":"proj-1"/)
})

test("retryTask forces a new resume run", async () => {
  let seenBody = null
  globalThis.fetch = async (_url, options = {}) => {
    seenBody = options.body
    return {
      ok: true,
      status: 200,
      async text() {
        return JSON.stringify({ run_id: "run-1" })
      },
    }
  }

  const client = createDevplaneClient({ baseUrl: "http://api:8080" })
  await client.retryTask("task-1")
  assert.match(String(seenBody), /"force_new_run":true/)
})

test("inspectWorkspace resolves task, run, and workspace payload", async () => {
  const responses = [
    {
      current_run_id: "run-1",
      task_id: "task-1",
    },
    {
      run_id: "run-1",
      workspace: {
        worktree_path: "/tmp/worktree",
        branch_name: "birtha/task-1",
      },
    },
  ]
  globalThis.fetch = async () => ({
    ok: true,
    status: 200,
    async text() {
      return JSON.stringify(responses.shift())
    },
  })

  const client = createDevplaneClient({ baseUrl: "http://api:8080" })
  const result = await client.inspectWorkspace("task-1")
  assert.equal(result.workspace.worktree_path, "/tmp/worktree")
})

test("format helpers stay compact", () => {
  assert.match(formatForText({ ok: true }), /```json/)
  assert.equal(
    summarizeStatus([{}], [{}, {}], [{}]),
    "Projects: 1\nTasks: 2\nRuns: 1",
  )
})
