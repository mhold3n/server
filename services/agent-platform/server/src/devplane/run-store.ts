import crypto from "node:crypto"
import type {
  ArtifactRecord,
  BackendRunSnapshot,
  BackendRunStatus,
  CommandExecution,
  DevPlaneRunCreatePayload,
  FileChange,
  RunPhase,
  VerificationResult,
} from "./types.js"

export interface BackendRunRecord extends BackendRunSnapshot {
  readonly request: DevPlaneRunCreatePayload
  readonly created_at: string
  updated_at: string
  finished_at?: string
  commands: CommandExecution[]
  callback_errors: string[]
  cancel_requested: boolean
}

const runs = new Map<string, BackendRunRecord>()

function nowIso(): string {
  return new Date().toISOString()
}

export function createBackendRun(request: DevPlaneRunCreatePayload): BackendRunRecord {
  const timestamp = nowIso()
  const record: BackendRunRecord = {
    run_id: crypto.randomUUID(),
    control_run_id: request.control_run_id,
    status: "queued",
    phase: "planning",
    engagement_mode: request.engagement_mode,
    engagement_mode_source: request.engagement_mode_source,
    engagement_mode_confidence: request.engagement_mode_confidence,
    engagement_mode_reasons: request.engagement_mode_reasons ?? [],
    minimum_engagement_mode: request.minimum_engagement_mode,
    pending_mode_change: request.pending_mode_change,
    lifecycle_reason: request.lifecycle_reason,
    lifecycle_detail: request.lifecycle_detail ?? {},
    summary: undefined,
    files_changed: [],
    verification_results: [],
    artifacts: [],
    request,
    created_at: timestamp,
    updated_at: timestamp,
    commands: [],
    callback_errors: [],
    cancel_requested: false,
  }
  runs.set(record.run_id, record)
  return record
}

export function getBackendRun(runId: string): BackendRunRecord | undefined {
  return runs.get(runId)
}

export function updateBackendRun(
  runId: string,
  patch: Partial<
    Pick<
      BackendRunRecord,
      | "status"
      | "phase"
      | "engagement_mode"
      | "engagement_mode_source"
      | "engagement_mode_confidence"
      | "engagement_mode_reasons"
      | "minimum_engagement_mode"
      | "pending_mode_change"
      | "lifecycle_reason"
      | "lifecycle_detail"
      | "summary"
      | "files_changed"
      | "verification_results"
      | "artifacts"
      | "commands"
      | "callback_errors"
      | "cancel_requested"
    >
  >,
): BackendRunRecord | undefined {
  const record = runs.get(runId)
  if (record === undefined) return undefined
  const nextStatus = patch.status ?? record.status
  const updated: BackendRunRecord = {
    ...record,
    ...patch,
    status: nextStatus,
    updated_at: nowIso(),
  }
  if (isTerminalStatus(nextStatus) && updated.finished_at === undefined) {
    updated.finished_at = updated.updated_at
  }
  runs.set(runId, updated)
  return updated
}

export function markRunCancelled(runId: string): BackendRunRecord | undefined {
  return updateBackendRun(runId, {
    cancel_requested: true,
    status: "cancelled",
    phase: "cancelled",
    summary: "Cancellation requested by control plane.",
    lifecycle_reason: "cancel_requested",
  })
}

export function appendRunCommands(
  runId: string,
  commands: CommandExecution[],
): BackendRunRecord | undefined {
  const record = runs.get(runId)
  if (record === undefined) return undefined
  return updateBackendRun(runId, {
    commands: [...record.commands, ...commands],
  })
}

export function appendCallbackError(
  runId: string,
  message: string,
): BackendRunRecord | undefined {
  const record = runs.get(runId)
  if (record === undefined) return undefined
  return updateBackendRun(runId, {
    callback_errors: [...record.callback_errors, message],
  })
}

export function completeBackendRun(
  runId: string,
  payload: {
    status: Extract<BackendRunStatus, "ready_to_publish" | "failed" | "cancelled">
    phase: RunPhase
    summary: string
    filesChanged: FileChange[]
    verificationResults: VerificationResult[]
    artifacts: ArtifactRecord[]
    commands: CommandExecution[]
  },
): BackendRunRecord | undefined {
  return updateBackendRun(runId, {
    status: payload.status,
    phase: payload.phase,
    summary: payload.summary,
    files_changed: payload.filesChanged,
    verification_results: payload.verificationResults,
    artifacts: payload.artifacts,
    commands: payload.commands,
  })
}

export function listBackendRuns(): BackendRunRecord[] {
  return Array.from(runs.values()).sort((left, right) =>
    right.updated_at.localeCompare(left.updated_at),
  )
}

function isTerminalStatus(status: BackendRunStatus): boolean {
  return (
    status === "ready_to_publish" ||
    status === "failed" ||
    status === "cancelled"
  )
}
