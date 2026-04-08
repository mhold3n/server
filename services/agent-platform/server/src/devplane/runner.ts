import { spawn } from "node:child_process"
import { mkdir, readFile, writeFile } from "node:fs/promises"
import path from "node:path"
import { OpenMultiAgent } from "@server/open-multi-agent"
import type { PlatformConfig } from "../config.js"
import {
  appendCallbackError,
  completeBackendRun,
  getBackendRun,
  updateBackendRun,
  type BackendRunRecord,
} from "./run-store.js"
import type {
  ArtifactRecord,
  CommandExecution,
  DevPlaneRunCreatePayload,
  FileChange,
  RunPhase,
  VerificationResult,
} from "./types.js"
import { createWorkspaceTools } from "./workspace-tools.js"

const MAX_EXCERPT_CHARS = 8_000
const CALLBACK_TIMEOUT_MS = 150

interface ExecuteRunOptions {
  cfg: PlatformConfig
  defaultModel: string
  defaultProvider: "anthropic" | "openai"
}

interface ExecutionAccumulator {
  commands: CommandExecution[]
  verificationResults: VerificationResult[]
  artifacts: ArtifactRecord[]
}

interface ActiveTaskPacket {
  objective?: string
  constraints?: string[]
  acceptance_criteria?: string[]
  context_summary?: string
  code_guidance?: {
    implementation_hints?: string[]
    target_paths?: string[]
  }
}

interface TaskPacketManifest {
  active_task_packet?: ActiveTaskPacket
  active_task_packet_ref?: string
  problem_brief_ref?: string
  engineering_state_ref?: string
}

export async function executeBackendRun(
  backendRunId: string,
  options: ExecuteRunOptions,
): Promise<void> {
  const record = getBackendRun(backendRunId)
  if (record === undefined) return

  updateBackendRun(backendRunId, {
    status: "running",
    phase: "planning",
    summary: "Internal task-agent run queued in agent-platform.",
  })

  const accumulator: ExecutionAccumulator = {
    commands: [],
    verificationResults: [],
    artifacts: [],
  }

  await postEvent(record, {
    phase: "planning",
    message: "Internal task-agent run started.",
  })

  try {
    await executeImplementationPhase(record, options, accumulator)

    if (isCancelRequested(backendRunId)) {
      await finalizeRun(record, accumulator, {
        status: "cancelled",
        phase: "cancelled",
        summary: "Run cancelled before verification completed.",
      })
      return
    }

    updateBackendRun(backendRunId, {
      phase: "verifying",
      summary: "Running deterministic verification commands.",
    })
    const verificationResults = await runVerification(record.request, accumulator)
    accumulator.verificationResults.push(...verificationResults)
    const filesChanged = await detectFileChanges(record.request.workspace.worktree_path)
    const artifact = await writeSummaryArtifact(record.request, accumulator, filesChanged)
    accumulator.artifacts.push(artifact)

    await postEvent(record, {
      phase: "verifying",
      message: "Captured implementation evidence and verification results.",
      commands: accumulator.commands,
      files_changed: filesChanged,
      verification_results: verificationResults,
      artifacts: accumulator.artifacts,
    })

    const hasFailedVerification = verificationResults.some(
      (result) => result.status === "failed",
    )
    if (hasFailedVerification) {
      await finalizeRun(record, accumulator, {
        status: "failed",
        phase: "failed",
        summary: "One or more verification commands failed.",
        filesChanged,
      })
      return
    }

    await finalizeRun(record, accumulator, {
      status: "ready_to_publish",
      phase: "ready_to_publish",
      summary: "Implementation finished and verification completed successfully.",
      filesChanged,
    })
  } catch (error) {
    const summary =
      error instanceof Error ? error.message : String(error)
    await finalizeRun(record, accumulator, {
      status: "failed",
      phase: "failed",
      summary: `Internal task-agent execution failed: ${summary}`,
    })
  }
}

async function executeImplementationPhase(
  record: BackendRunRecord,
  options: ExecuteRunOptions,
  accumulator: ExecutionAccumulator,
): Promise<void> {
  updateBackendRun(record.run_id, {
    phase: "implementing",
    summary: "Executing implementation agents in the isolated workspace.",
  })
  await postEvent(record, {
    phase: "implementing",
    message: "Implementation phase started.",
  })

  const workspaceRoot = record.request.workspace.worktree_path
  const onCommand = (command: CommandExecution): void => {
    accumulator.commands.push(command)
  }
  const manifest = await readTaskPacketManifest(record.request.task_packet_path)
  const effectiveObjective = manifest?.active_task_packet?.objective ?? record.request.plan.objective

  if (shouldUseMockExecutor(options.defaultProvider, options.cfg.llmBackend)) {
    const notePath = path.join(workspaceRoot, ".birtha", "mock-agent-notes.md")
    await mkdir(path.dirname(notePath), { recursive: true })
    await writeFile(
      notePath,
      [
        "# Internal Task-Agent Stub",
        "",
        "The agent-platform run executed in mock mode.",
        "",
        `Objective: ${effectiveObjective}`,
      ].join("\n"),
      "utf8",
    )
    accumulator.artifacts.push({
      name: "mock-agent-notes",
      path: notePath,
      kind: "run_notes",
      description: "Mock-mode execution note emitted by the internal task-agent runtime.",
    })
    return
  }

  const tools = createWorkspaceTools(workspaceRoot, { onCommand })
  const orchestration = new OpenMultiAgent({
    defaultModel: options.defaultModel,
    defaultProvider: options.defaultProvider,
    enableBuiltInTools: false,
    extraTools: tools,
  })
  const toolNames = tools.map((tool) => tool.name)
  const team = orchestration.createTeam(`devplane-${record.request.task_id}`, {
    name: "devplane-code-task",
    sharedMemory: true,
    maxConcurrency: 2,
    agents: [
      {
        name: "lead_executor",
        model: options.defaultModel,
        provider: options.defaultProvider,
        systemPrompt: buildLeadSystemPrompt(record.request.workspace.worktree_path),
        tools: toolNames,
        maxTurns: 10,
      },
      {
        name: "reviewer",
        model: options.defaultModel,
        provider: options.defaultProvider,
        systemPrompt: buildReviewerSystemPrompt(record.request.workspace.worktree_path),
        tools: [
          "workspace_find_files",
          "workspace_file_read",
          "workspace_git_status",
          "workspace_bash",
        ],
        maxTurns: 6,
      },
    ],
  })

  const result = await orchestration.runTasks(team, [
      {
        title: "Implement requested changes",
        description: buildImplementationTask(record.request, manifest),
        assignee: "lead_executor",
      },
      {
        title: "Review workspace readiness",
        description: buildReviewTask(record.request, manifest),
        assignee: "reviewer",
        dependsOn: ["Implement requested changes"],
      },
  ])

  const summaryPath = path.join(workspaceRoot, ".birtha", "agent-platform-output.md")
  await mkdir(path.dirname(summaryPath), { recursive: true })
  await writeFile(
    summaryPath,
    [
      "# Agent Platform Output",
      "",
      "## Lead Executor",
      "",
      result.agentResults.get("lead_executor")?.output ?? "(no lead output)",
      "",
      "## Reviewer",
      "",
      result.agentResults.get("reviewer")?.output ?? "(no reviewer output)",
    ].join("\n"),
    "utf8",
  )
  accumulator.artifacts.push({
    name: "agent-platform-output",
    path: summaryPath,
    kind: "run_summary",
    description: "Combined agent outputs from the internal task-agent runtime.",
  })
}

async function runVerification(
  request: DevPlaneRunCreatePayload,
  accumulator: ExecutionAccumulator,
): Promise<VerificationResult[]> {
  const commands =
    request.plan.verification_blocks.length > 0
      ? request.plan.verification_blocks.map((block) => ({
          name: block.name,
          command: block.command,
        }))
      : request.plan.verification_plan.map((command, index) => ({
          name: `verification_${index + 1}`,
          command,
        }))

  if (commands.length === 0) {
    return [
      {
        name: "verification",
        command: null,
        status: "skipped",
        exit_code: null,
        stdout_excerpt: "No verification commands were provided.",
        stderr_excerpt: null,
      },
    ]
  }

  const results: VerificationResult[] = []
  for (const item of commands) {
    const command = await runCommand(item.command, request.workspace.worktree_path)
    accumulator.commands.push(command)
    results.push({
      name: item.name,
      command: item.command,
      status: (command.exit_code ?? 1) === 0 ? "passed" : "failed",
      exit_code: command.exit_code ?? 1,
      stdout_excerpt: command.stdout_excerpt ?? null,
      stderr_excerpt: command.stderr_excerpt ?? null,
    })
  }
  return results
}

async function finalizeRun(
  record: BackendRunRecord,
  accumulator: ExecutionAccumulator,
  outcome: {
    status: "ready_to_publish" | "failed" | "cancelled"
    phase: RunPhase
    summary: string
    filesChanged?: FileChange[]
  },
): Promise<void> {
  const effectiveOutcome =
    isCancelRequested(record.run_id) && outcome.status !== "failed"
      ? {
          ...outcome,
          status: "cancelled" as const,
          phase: "cancelled" as const,
          summary:
            outcome.status === "cancelled"
              ? outcome.summary
              : "Run cancelled by control plane.",
        }
      : outcome
  const filesChanged =
    effectiveOutcome.filesChanged ??
    (await detectFileChanges(record.request.workspace.worktree_path))
  completeBackendRun(record.run_id, {
    status: effectiveOutcome.status,
    phase: effectiveOutcome.phase,
    summary: effectiveOutcome.summary,
    filesChanged,
    verificationResults: accumulator.verificationResults,
    artifacts: accumulator.artifacts,
    commands: accumulator.commands,
  })

  await postComplete(record, {
    status:
      effectiveOutcome.status === "ready_to_publish"
        ? "ready_to_publish"
        : effectiveOutcome.status,
    phase: effectiveOutcome.phase,
    summary: effectiveOutcome.summary,
    files_changed: filesChanged,
    verification_results: accumulator.verificationResults,
    artifacts: accumulator.artifacts,
  })
}

async function postEvent(
  record: BackendRunRecord,
  payload: {
    phase: RunPhase
    message: string
    commands?: CommandExecution[]
    files_changed?: FileChange[]
    verification_results?: VerificationResult[]
    artifacts?: ArtifactRecord[]
  },
): Promise<void> {
  try {
    const response = await fetch(record.request.callback.events_url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(CALLBACK_TIMEOUT_MS),
    })
    if (!response.ok) {
      appendCallbackError(
        record.run_id,
        `Event callback failed with HTTP ${response.status}.`,
      )
    }
  } catch (error) {
    appendCallbackError(
      record.run_id,
      `Event callback error: ${error instanceof Error ? error.message : String(error)}`,
    )
  }
}

async function postComplete(
  record: BackendRunRecord,
  payload: {
    status: "ready_to_publish" | "failed" | "cancelled"
    phase: RunPhase
    summary: string
    files_changed: FileChange[]
    verification_results: VerificationResult[]
    artifacts: ArtifactRecord[]
  },
): Promise<void> {
  try {
    const response = await fetch(record.request.callback.complete_url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(CALLBACK_TIMEOUT_MS),
    })
    if (!response.ok) {
      appendCallbackError(
        record.run_id,
        `Completion callback failed with HTTP ${response.status}.`,
      )
    }
  } catch (error) {
    appendCallbackError(
      record.run_id,
      `Completion callback error: ${error instanceof Error ? error.message : String(error)}`,
    )
  }
}

async function writeSummaryArtifact(
  request: DevPlaneRunCreatePayload,
  accumulator: ExecutionAccumulator,
  filesChanged: FileChange[],
): Promise<ArtifactRecord> {
  const summaryPath = path.join(
    request.workspace.worktree_path,
    ".birtha",
    "agent-platform-run.json",
  )
  await mkdir(path.dirname(summaryPath), { recursive: true })
  await writeFile(
    summaryPath,
    JSON.stringify(
      {
        task_id: request.task_id,
        objective: request.plan.objective,
        command_count: accumulator.commands.length,
        verification_results: accumulator.verificationResults,
        files_changed: filesChanged,
      },
      null,
      2,
    ),
    "utf8",
  )
  return {
    name: "agent-platform-run",
    path: summaryPath,
    kind: "run_manifest",
    description: "Serialized manifest from the internal task-agent execution backend.",
  }
}

async function detectFileChanges(worktreePath: string): Promise<FileChange[]> {
  const statusCommand = await runCommand("git status --porcelain", worktreePath)
  const output = statusCommand.stdout_excerpt ?? ""
  if (output.trim().length === 0) {
    return []
  }
  return output
    .split("\n")
    .filter((line) => line.trim().length >= 3)
    .map((line) => {
      const gitStatus = line.slice(0, 2)
      const filePath = line.slice(3)
      return {
        path: filePath,
        change_type: mapPorcelainStatus(gitStatus),
        git_status: gitStatus,
      }
    })
}

async function runCommand(
  command: string,
  cwd: string,
): Promise<CommandExecution> {
  const result = await new Promise<{
    stdout: string
    stderr: string
    exitCode: number
  }>((resolve) => {
    const stdoutChunks: Buffer[] = []
    const stderrChunks: Buffer[] = []
    const child = spawn("bash", ["-lc", command], {
      cwd,
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
    })
    child.stdout.on("data", (chunk: Buffer) => stdoutChunks.push(chunk))
    child.stderr.on("data", (chunk: Buffer) => stderrChunks.push(chunk))
    child.on("close", (code) => {
      resolve({
        stdout: Buffer.concat(stdoutChunks).toString("utf8"),
        stderr: Buffer.concat(stderrChunks).toString("utf8"),
        exitCode: code ?? 1,
      })
    })
    child.on("error", (error) => {
      resolve({
        stdout: "",
        stderr: error.message,
        exitCode: 127,
      })
    })
  })

  return {
    command,
    cwd,
    exit_code: result.exitCode,
    stdout_excerpt: excerpt(result.stdout),
    stderr_excerpt: excerpt(result.stderr),
    source: "agent-platform",
  }
}

function shouldUseMockExecutor(
  defaultProvider: "anthropic" | "openai",
  llmBackend: string,
): boolean {
  if (llmBackend === "mock" || llmBackend === "none" || llmBackend === "disabled") {
    return true
  }
  if (defaultProvider === "openai") {
    return !process.env.OPENAI_API_KEY
  }
  return !process.env.ANTHROPIC_API_KEY
}

function buildLeadSystemPrompt(workspaceRoot: string): string {
  return [
    "You are the internal implementation agent for a controlled dev-plane run.",
    `Only operate inside this workspace: ${workspaceRoot}`,
    "Use only the provided workspace_* tools.",
    "Do not publish, push, open pull requests, or reference files outside the workspace.",
    "Make the minimum changes needed to satisfy the task objective.",
  ].join(" ")
}

function buildReviewerSystemPrompt(workspaceRoot: string): string {
  return [
    "You are the non-authoritative reviewer for an internal dev-plane run.",
    `You may inspect only this workspace: ${workspaceRoot}`,
    "Do not edit files unless absolutely necessary; prefer reporting risks and readiness.",
    "Do not publish or push changes.",
  ].join(" ")
}

function buildImplementationTask(
  request: DevPlaneRunCreatePayload,
  manifest?: TaskPacketManifest,
): string {
  const activeTaskPacket = manifest?.active_task_packet
  const objective = activeTaskPacket?.objective ?? request.plan.objective
  const constraints =
    activeTaskPacket?.constraints && activeTaskPacket.constraints.length > 0
      ? activeTaskPacket.constraints
      : request.plan.constraints
  const acceptanceCriteria =
    activeTaskPacket?.acceptance_criteria && activeTaskPacket.acceptance_criteria.length > 0
      ? activeTaskPacket.acceptance_criteria
      : request.plan.acceptance_criteria
  const implementationHints =
    activeTaskPacket?.code_guidance?.implementation_hints &&
    activeTaskPacket.code_guidance.implementation_hints.length > 0
      ? activeTaskPacket.code_guidance.implementation_hints
      : request.plan.implementation_outline
  return [
    `Objective: ${objective}`,
    activeTaskPacket?.context_summary
      ? `Task packet context:\n${activeTaskPacket.context_summary}`
      : "",
    constraints.length > 0
      ? `Constraints:\n- ${constraints.join("\n- ")}`
      : "Constraints: none provided.",
    acceptanceCriteria.length > 0
      ? `Acceptance criteria:\n- ${acceptanceCriteria.join("\n- ")}`
      : "Acceptance criteria: satisfy the task packet and preserve workspace safety.",
    request.plan.delegation_hints.length > 0
      ? `Delegation hints:\n- ${request.plan.delegation_hints.join("\n- ")}`
      : "Delegation hints: keep implementation ownership with the lead executor.",
    implementationHints.length > 0
      ? `Implementation outline:\n- ${implementationHints.join("\n- ")}`
      : "",
    manifest?.active_task_packet_ref
      ? `Active governed task packet: ${manifest.active_task_packet_ref}`
      : "",
    "Use workspace_git_status before and after meaningful edits.",
    "Leave the branch ready for deterministic verification by the control plane.",
  ]
    .filter(Boolean)
    .join("\n\n")
}

function buildReviewTask(
  request: DevPlaneRunCreatePayload,
  manifest?: TaskPacketManifest,
): string {
  const objective = manifest?.active_task_packet?.objective ?? request.plan.objective
  return [
    `Review the workspace for task objective: ${objective}`,
    "Confirm whether the current state appears ready for deterministic verification and publish handoff.",
    "Summarize any remaining risk, missing tests, or suspicious file changes.",
    manifest?.active_task_packet_ref
      ? `Active governed task packet: ${manifest.active_task_packet_ref}`
      : "",
    request.task_packet_path
      ? `Task packet path: ${request.task_packet_path}`
      : "",
  ]
    .filter(Boolean)
    .join("\n\n")
}

function mapPorcelainStatus(status: string): string {
  if (status.includes("A")) return "added"
  if (status.includes("M")) return "modified"
  if (status.includes("D")) return "deleted"
  if (status.includes("R")) return "renamed"
  if (status === "??") return "untracked"
  return "unknown"
}

function excerpt(value: string): string | undefined {
  if (value.length === 0) return undefined
  if (value.length <= MAX_EXCERPT_CHARS) {
    return value
  }
  return `${value.slice(0, MAX_EXCERPT_CHARS)}\n...<truncated>`
}

async function readTaskPacketManifest(
  taskPacketPath: string | null | undefined,
): Promise<TaskPacketManifest | undefined> {
  if (!taskPacketPath) return undefined
  try {
    const raw = await readFile(taskPacketPath, "utf8")
    return JSON.parse(raw) as TaskPacketManifest
  } catch {
    return undefined
  }
}

function isCancelRequested(runId: string): boolean {
  return getBackendRun(runId)?.cancel_requested === true
}
