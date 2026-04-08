import { z } from "zod"

export const runPhaseSchema = z.enum([
  "planning",
  "implementing",
  "verifying",
  "ready_to_publish",
  "published",
  "failed",
  "cancelled",
])

export const backendRunStatusSchema = z.enum([
  "queued",
  "running",
  "ready_to_publish",
  "failed",
  "cancelled",
])

export const workspaceSchema = z.object({
  canonical_repo_path: z.string(),
  worktree_path: z.string(),
  branch_name: z.string(),
  base_branch: z.string(),
  remote_name: z.string().default("origin"),
})

export const verificationBlockSchema = z.object({
  name: z.string(),
  command: z.string(),
  required: z.boolean().default(true),
})

export const taskPlanSchema = z.object({
  project_id: z.string(),
  objective: z.string(),
  constraints: z.array(z.string()).default([]),
  acceptance_criteria: z.array(z.string()).default([]),
  implementation_outline: z.array(z.string()).default([]),
  verification_plan: z.array(z.string()).default([]),
  delegation_hints: z.array(z.string()).default([]),
  work_items: z.array(z.string()).default([]),
  verification_blocks: z.array(verificationBlockSchema).default([]),
  repo_ref_hint: z.string().nullable().optional(),
  planned_branch: z.string().nullable().optional(),
})

export const patchOperationSchema = z.object({
  file_path: z.string(),
  operation: z.string(),
  summary: z.string().nullable().optional(),
  requires_approval: z.boolean().default(false),
})

export const patchPlanSchema = z.object({
  plan_id: z.string(),
  patches: z.array(patchOperationSchema).default([]),
  validation_status: z.string().default("pending"),
})

export const callbackSchema = z.object({
  events_url: z.string().url(),
  complete_url: z.string().url(),
})

export const devPlaneRunCreateSchema = z.object({
  control_run_id: z.string(),
  task_id: z.string(),
  project_id: z.string(),
  workspace: workspaceSchema,
  plan: taskPlanSchema,
  patch_plan: patchPlanSchema.nullable().optional(),
  task_packet_path: z.string().nullable().optional(),
  callback: callbackSchema,
})

export const commandExecutionSchema = z.object({
  command: z.string(),
  cwd: z.string(),
  exit_code: z.number().int().nullable().optional(),
  stdout_excerpt: z.string().nullable().optional(),
  stderr_excerpt: z.string().nullable().optional(),
  source: z.string().default("agent-platform"),
})

export const fileChangeSchema = z.object({
  path: z.string(),
  change_type: z.string(),
  git_status: z.string().nullable().optional(),
})

export const verificationResultSchema = z.object({
  name: z.string(),
  command: z.string().nullable().optional(),
  status: z.enum(["pending", "passed", "failed", "skipped"]),
  exit_code: z.number().int().nullable().optional(),
  stdout_excerpt: z.string().nullable().optional(),
  stderr_excerpt: z.string().nullable().optional(),
})

export const artifactSchema = z.object({
  name: z.string(),
  path: z.string(),
  kind: z.string(),
  description: z.string().nullable().optional(),
})

export const backendRunSnapshotSchema = z.object({
  run_id: z.string(),
  control_run_id: z.string(),
  status: backendRunStatusSchema,
  phase: runPhaseSchema.nullable().optional(),
  summary: z.string().nullable().optional(),
  files_changed: z.array(fileChangeSchema).default([]),
  verification_results: z.array(verificationResultSchema).default([]),
  artifacts: z.array(artifactSchema).default([]),
})

export type RunPhase = z.infer<typeof runPhaseSchema>
export type BackendRunStatus = z.infer<typeof backendRunStatusSchema>
export type WorkspacePayload = z.infer<typeof workspaceSchema>
export type VerificationBlock = z.infer<typeof verificationBlockSchema>
export type TaskPlanPayload = z.infer<typeof taskPlanSchema>
export type PatchPlanPayload = z.infer<typeof patchPlanSchema>
export type DevPlaneRunCreatePayload = z.infer<typeof devPlaneRunCreateSchema>
export type CommandExecution = z.infer<typeof commandExecutionSchema>
export type FileChange = z.infer<typeof fileChangeSchema>
export type VerificationResult = z.infer<typeof verificationResultSchema>
export type ArtifactRecord = z.infer<typeof artifactSchema>
export type BackendRunSnapshot = z.infer<typeof backendRunSnapshotSchema>
