import fs from "node:fs"
import path from "node:path"

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

/** When set, workflow runs are persisted as JSON for audit/rehydration (DevPlane-aligned). */
const persistDir = process.env.WORKFLOW_RUN_STORE_DIR

function fileFor(id: string): string | null {
  if (!persistDir) {
    return null
  }
  return path.join(persistDir, `${id}.json`)
}

function writeDisk(rec: WorkflowRecord): void {
  const fp = fileFor(rec.id)
  if (!fp) {
    return
  }
  fs.mkdirSync(path.dirname(fp), { recursive: true })
  fs.writeFileSync(fp, JSON.stringify(rec, null, 2), "utf8")
}

function readDisk(id: string): WorkflowRecord | null {
  const fp = fileFor(id)
  if (!fp || !fs.existsSync(fp)) {
    return null
  }
  const raw = fs.readFileSync(fp, "utf8")
  return JSON.parse(raw) as WorkflowRecord
}

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
  writeDisk(rec)
  return rec
}

export function completeWorkflowRun(id: string, result: unknown): void {
  const rec = store.get(id) ?? readDisk(id)
  if (!rec) {
    return
  }
  rec.status = rec.cancelled ? "cancelled" : "completed"
  rec.finishedAt = Date.now()
  rec.result = result
  store.set(id, rec)
  writeDisk(rec)
}

export function failWorkflowRun(id: string, error: string): void {
  const rec = store.get(id) ?? readDisk(id)
  if (!rec) {
    return
  }
  rec.status = "failed"
  rec.finishedAt = Date.now()
  rec.result = { error }
  store.set(id, rec)
  writeDisk(rec)
}

export function cancelWorkflowRun(id: string): boolean {
  const rec = store.get(id) ?? readDisk(id)
  if (!rec || rec.status === "completed" || rec.status === "failed") {
    return false
  }
  rec.cancelled = true
  if (rec.status === "running") {
    rec.status = "cancelled"
    rec.finishedAt = Date.now()
  }
  store.set(id, rec)
  writeDisk(rec)
  return true
}

export function getWorkflowRun(id: string): WorkflowRecord | undefined {
  const mem = store.get(id)
  if (mem) {
    return mem
  }
  const disk = readDisk(id)
  if (disk) {
    store.set(id, disk)
    return disk
  }
  return undefined
}
