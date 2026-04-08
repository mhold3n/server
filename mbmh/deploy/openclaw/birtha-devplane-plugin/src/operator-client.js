const DEFAULT_BASE_URL = "http://api:8080"
const DEFAULT_TIMEOUT_MS = 30_000

export function createDevplaneClient(config = {}) {
  const baseUrl = String(config.baseUrl ?? DEFAULT_BASE_URL).replace(/\/$/, "")
  const requestTimeoutMs = Number(config.requestTimeoutMs ?? DEFAULT_TIMEOUT_MS)

  async function request(path, options = {}) {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), requestTimeoutMs)
    try {
      const response = await fetch(`${baseUrl}${path}`, {
        ...options,
        headers: {
          "Content-Type": "application/json",
          ...(options.headers ?? {}),
        },
        signal: controller.signal,
      })
      const text = await response.text()
      const payload = text.length > 0 ? JSON.parse(text) : null
      if (!response.ok) {
        throw new Error(
          `Birtha control plane HTTP ${response.status}: ${text || response.statusText}`,
        )
      }
      return payload
    } finally {
      clearTimeout(timer)
    }
  }

  return {
    listProjects() {
      return request("/api/dev/projects")
    },
    registerProject(payload) {
      return request("/api/dev/projects", {
        method: "POST",
        body: JSON.stringify(payload),
      })
    },
    listTasks() {
      return request("/api/dev/tasks")
    },
    submitTask(payload) {
      return request("/api/dev/tasks", {
        method: "POST",
        body: JSON.stringify(payload),
      })
    },
    answerClarifications(taskId, payload) {
      return request(`/api/dev/tasks/${taskId}/answer`, {
        method: "POST",
        body: JSON.stringify(payload),
      })
    },
    getTask(taskId) {
      return request(`/api/dev/tasks/${taskId}`)
    },
    cancelTask(taskId) {
      return request(`/api/dev/tasks/${taskId}/cancel`, {
        method: "POST",
        body: JSON.stringify({}),
      })
    },
    retryTask(taskId) {
      return request(`/api/dev/tasks/${taskId}/resume`, {
        method: "POST",
        body: JSON.stringify({ force_new_run: true }),
      })
    },
    getRun(runId) {
      return request(`/api/dev/runs/${runId}`)
    },
    listRuns() {
      return request("/api/dev/runs")
    },
    getDossier(taskId) {
      return request(`/api/dev/tasks/${taskId}/dossier`)
    },
    publishTask(taskId, payload) {
      return request(`/api/dev/tasks/${taskId}/publish`, {
        method: "POST",
        body: JSON.stringify(payload),
      })
    },
    async inspectWorkspace(taskId) {
      const task = await request(`/api/dev/tasks/${taskId}`)
      if (!task.current_run_id) {
        return { task, run: null, workspace: null }
      }
      const run = await request(`/api/dev/runs/${task.current_run_id}`)
      return { task, run, workspace: run.workspace ?? null }
    },
  }
}

export function formatForText(value) {
  return `\`\`\`json\n${JSON.stringify(value, null, 2)}\n\`\`\``
}

export function summarizeStatus(projects, tasks, runs) {
  return [
    `Projects: ${projects.length}`,
    `Tasks: ${tasks.length}`,
    `Runs: ${runs.length}`,
  ].join("\n")
}
