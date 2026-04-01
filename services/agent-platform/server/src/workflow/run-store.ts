export type WorkflowRecord = {
  id: string
  workflow_name: string
  status: "pending" | "running" | "completed" | "cancelled" | "failed"
  startedAt: number
  finishedAt?: number
  result?: unknown
  cancelled?: boolean
}

const store = new Map<string, WorkflowRecord>()

export function createWorkflowRun(
  id: string,
  workflowName: string,
): WorkflowRecord {
  const rec: WorkflowRecord = {
    id,
    workflow_name: workflowName,
    status: "running",
    startedAt: Date.now(),
  }
  store.set(id, rec)
  return rec
}

export function completeWorkflowRun(id: string, result: unknown): void {
  const rec = store.get(id)
  if (!rec) return
  rec.status = rec.cancelled ? "cancelled" : "completed"
  rec.finishedAt = Date.now()
  rec.result = result
}

export function failWorkflowRun(id: string, error: string): void {
  const rec = store.get(id)
  if (!rec) return
  rec.status = "failed"
  rec.finishedAt = Date.now()
  rec.result = { error }
}

export function cancelWorkflowRun(id: string): boolean {
  const rec = store.get(id)
  if (!rec || rec.status === "completed" || rec.status === "failed") {
    return false
  }
  rec.cancelled = true
  if (rec.status === "running") {
    rec.status = "cancelled"
    rec.finishedAt = Date.now()
  }
  return true
}

export function getWorkflowRun(id: string): WorkflowRecord | undefined {
  return store.get(id)
}
