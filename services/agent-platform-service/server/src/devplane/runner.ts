import { spawn } from "node:child_process"
import { mkdir, readFile, writeFile } from "node:fs/promises"
import path from "node:path"
import type { PlatformConfig } from "../config.js"
import { LLMManager } from "../llm/manager.js"
import { OrchestrationEngine } from "../orchestration/engine.js"
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
}

interface ExecutionAccumulator {
  commands: CommandExecution[]
  verificationResults: VerificationResult[]
  artifacts: ArtifactRecord[]
}

interface ActiveTaskPacket {
  task_packet_id?: string
  objective?: string
  constraints?: string[]
  acceptance_criteria?: string[]
  context_summary?: string
  routing_metadata?: {
    selected_executor?: string
  }
  required_outputs?: Array<{
    artifact_type?: string
  }>
  validation_requirements?: string[]
  code_guidance?: {
    implementation_hints?: string[]
    target_paths?: string[]
  }
  response_control_ref?: string
  selected_knowledge_pool_refs?: string[]
  selected_module_refs?: string[]
  selected_technique_refs?: string[]
  selected_theory_refs?: string[]
  knowledge_context?: {
    assessment_ref?: string
    candidate_pack_refs?: string[]
    role_context_ref?: string
    role_context_summary?: string
    preferred_adapter_ref?: string
    preferred_environment_ref?: string
    runtime_verification_refs?: string[]
    coverage_class?: string
    required?: boolean
  }
}

interface TaskPacketManifest {
  active_task_packet?: ActiveTaskPacket
  active_task_packet_ref?: string
  problem_brief_ref?: string
  engineering_state_ref?: string
  knowledge_pool_assessment_ref?: string
  knowledge_pool_coverage?: string
  knowledge_candidate_refs?: string[]
  knowledge_role_context_refs?: string[]
  knowledge_gaps?: string[]
  knowledge_required?: boolean
  response_mode?: string
  response_control_ref?: string
  selected_knowledge_pool_refs?: string[]
  selected_module_refs?: string[]
  selected_technique_refs?: string[]
  selected_theory_refs?: string[]
  active_knowledge_assessment_ref?: string
  active_role_context_ref?: string
  active_preferred_adapter_ref?: string
  active_preferred_environment_ref?: string
  task_queue?: Record<string, unknown>
  task_packets_path?: string
  escalation_packets?: Array<Record<string, unknown>>
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
  const activeTaskPacket = manifest?.active_task_packet
  if (!activeTaskPacket) {
    await executeLegacyImplementationRun(record, options, accumulator, onCommand)
    return
  }
  const selectedExecutor =
    activeTaskPacket.routing_metadata?.selected_executor ?? ""
  if (!selectedExecutor) {
    throw new Error("Active governed task packet is missing routing_metadata.selected_executor.")
  }
  const responseControlRef =
    activeTaskPacket.response_control_ref ?? manifest?.response_control_ref
  const selectedPoolRefs =
    activeTaskPacket.selected_knowledge_pool_refs ?? manifest?.selected_knowledge_pool_refs ?? []
  const selectedTheoryRefs =
    activeTaskPacket.selected_theory_refs ?? manifest?.selected_theory_refs ?? []
  const selectedModuleRefs =
    activeTaskPacket.selected_module_refs ?? manifest?.selected_module_refs ?? []
  const knowledgeRequired = manifest?.knowledge_required === true || selectedPoolRefs.length > 0
  if (knowledgeRequired) {
    if (!responseControlRef) {
      throw new Error(
        "Active governed task packet requires response_control_ref before execution.",
      )
    }
    if (selectedPoolRefs.length === 0) {
      throw new Error(
        "Active governed task packet requires selected_knowledge_pool_refs before execution.",
      )
    }
    if (selectedTheoryRefs.length === 0) {
      throw new Error(
        "Active governed task packet requires selected_theory_refs before execution.",
      )
    }
    if (
      activeTaskPacket.routing_metadata?.selected_executor === "coding_model" &&
      selectedModuleRefs.length === 0
    ) {
      throw new Error(
        "Active governed coding task packet requires selected_module_refs before execution.",
      )
    }
  }
  const effectiveObjective = activeTaskPacket.objective ?? record.request.plan.objective

  if (shouldUseMockExecutor(options.cfg.llmBackend)) {
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
        `Selected executor: ${selectedExecutor}`,
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

  if (selectedExecutor === "coding_model") {
    await executeCodingModelRun(record, options, accumulator, manifest, onCommand)
    return
  }
  if (selectedExecutor === "local_general_model") {
    await executeLocalGeneralRun(record, options, accumulator, manifest, onCommand)
    return
  }
  if (selectedExecutor === "multimodal_model") {
    await executeMultimodalRun(record, options, accumulator, manifest)
    return
  }
  if (selectedExecutor === "deterministic_validator") {
    await executeValidatorNoop(record, accumulator, manifest)
    return
  }
  if (selectedExecutor === "strategic_reviewer") {
    await executeStrategicReviewerRun(record, options, accumulator, manifest, onCommand)
    return
  }

  throw new Error(`Unsupported strict engineering executor: ${selectedExecutor}`)
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
        status: "failed",
        exit_code: null,
        stdout_excerpt: null,
        stderr_excerpt:
          "Strict engineering execution requires deterministic verification commands.",
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
  llmBackend: string,
): boolean {
  return llmBackend === "mock" || llmBackend === "none" || llmBackend === "disabled"
}

function createRuntimeEngine(cfg: PlatformConfig): OrchestrationEngine {
  return new OrchestrationEngine(cfg, new LLMManager(cfg))
}

function buildCodingSystemPrompt(workspaceRoot: string): string {
  return [
    "You are the coding-model executor for a governed dev-plane run.",
    `Only operate inside this workspace: ${workspaceRoot}`,
    "Use only the provided workspace_* tools.",
    "Do not publish, push, open pull requests, or reference files outside the workspace.",
    "Make the minimum changes needed to satisfy the task objective.",
  ].join(" ")
}

function buildLocalGeneralSystemPrompt(workspaceRoot: string): string {
  return [
    "You are the local general-model executor for a governed dev-plane run.",
    `You may inspect only this workspace: ${workspaceRoot}`,
    "Use only read-only workspace tools.",
    "Do not edit files, publish changes, or invoke repository mutations.",
  ].join(" ")
}

function buildStrategicReviewSystemPrompt(workspaceRoot: string): string {
  return [
    "You are the strategic reviewer for a governed dev-plane escalation.",
    `You may inspect only this workspace: ${workspaceRoot}`,
    "Use only read-only workspace tools.",
    "Do not edit files, publish changes, or invoke repository mutations.",
    "Return compact decision guidance tied to the escalation packet only.",
  ].join(" ")
}

function buildImplementationTask(
  request: DevPlaneRunCreatePayload,
  manifest?: TaskPacketManifest,
): string {
  const activeTaskPacket = manifest?.active_task_packet
  if (!activeTaskPacket) {
    return "Strict engineering manifest is missing the active task packet."
  }
  const objective = activeTaskPacket.objective ?? request.plan.objective
  const constraints = activeTaskPacket.constraints ?? []
  const acceptanceCriteria = activeTaskPacket.acceptance_criteria ?? []
  const implementationHints =
    activeTaskPacket?.code_guidance?.implementation_hints &&
    activeTaskPacket.code_guidance.implementation_hints.length > 0
      ? activeTaskPacket.code_guidance.implementation_hints
      : []
  const responseControlRef =
    activeTaskPacket.response_control_ref ?? manifest?.response_control_ref
  const selectedPoolRefs =
    activeTaskPacket.selected_knowledge_pool_refs ?? manifest?.selected_knowledge_pool_refs ?? []
  const selectedModuleRefs =
    activeTaskPacket.selected_module_refs ?? manifest?.selected_module_refs ?? []
  const selectedTechniqueRefs =
    activeTaskPacket.selected_technique_refs ?? manifest?.selected_technique_refs ?? []
  const selectedTheoryRefs =
    activeTaskPacket.selected_theory_refs ?? manifest?.selected_theory_refs ?? []
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
    implementationHints.length > 0
      ? `Implementation outline:\n- ${implementationHints.join("\n- ")}`
      : "",
    responseControlRef ? `Response control ref: ${responseControlRef}` : "",
    manifest?.knowledge_pool_coverage
      ? `Knowledge coverage: ${manifest.knowledge_pool_coverage}`
      : "",
    selectedPoolRefs.length > 0
      ? `Selected knowledge pools:\n- ${selectedPoolRefs.join("\n- ")}`
      : "",
    selectedModuleRefs.length > 0
      ? `Selected modules:\n- ${selectedModuleRefs.join("\n- ")}`
      : "",
    selectedTechniqueRefs.length > 0
      ? `Selected techniques:\n- ${selectedTechniqueRefs.join("\n- ")}`
      : "",
    selectedTheoryRefs.length > 0
      ? `Selected theory basis:\n- ${selectedTheoryRefs.join("\n- ")}`
      : "",
    manifest?.active_task_packet_ref
      ? `Active governed task packet: ${manifest.active_task_packet_ref}`
      : "",
    manifest?.problem_brief_ref ? `Problem brief ref: ${manifest.problem_brief_ref}` : "",
    manifest?.engineering_state_ref
      ? `Engineering state ref: ${manifest.engineering_state_ref}`
      : "",
    "Use workspace_git_status before and after meaningful edits.",
    "Treat task.plan as supplemental only; the governed packet is authoritative.",
    "Leave the branch ready for deterministic verification by the control plane.",
  ]
    .filter(Boolean)
    .join("\n\n")
}

function buildReadOnlyTask(
  title: string,
  manifest?: TaskPacketManifest,
): string {
  const objective = manifest?.active_task_packet?.objective ?? "governed engineering task"
  const activeTaskPacket = manifest?.active_task_packet
  const responseControlRef = activeTaskPacket?.response_control_ref ?? manifest?.response_control_ref
  const selectedPoolRefs =
    activeTaskPacket?.selected_knowledge_pool_refs ?? manifest?.selected_knowledge_pool_refs ?? []
  const selectedModuleRefs =
    activeTaskPacket?.selected_module_refs ?? manifest?.selected_module_refs ?? []
  const selectedTechniqueRefs =
    activeTaskPacket?.selected_technique_refs ?? manifest?.selected_technique_refs ?? []
  const selectedTheoryRefs =
    activeTaskPacket?.selected_theory_refs ?? manifest?.selected_theory_refs ?? []
  return [
    `${title}: ${objective}`,
    manifest?.active_task_packet_ref
      ? `Active governed task packet: ${manifest.active_task_packet_ref}`
      : "",
    manifest?.problem_brief_ref
      ? `Problem brief ref: ${manifest.problem_brief_ref}`
      : "",
    manifest?.engineering_state_ref
      ? `Engineering state ref: ${manifest.engineering_state_ref}`
      : "",
    responseControlRef ? `Response control ref: ${responseControlRef}` : "",
    selectedPoolRefs.length > 0
      ? `Selected knowledge pools:\n- ${selectedPoolRefs.join("\n- ")}`
      : "",
    selectedModuleRefs.length > 0
      ? `Selected modules:\n- ${selectedModuleRefs.join("\n- ")}`
      : "",
    selectedTechniqueRefs.length > 0
      ? `Selected techniques:\n- ${selectedTechniqueRefs.join("\n- ")}`
      : "",
    selectedTheoryRefs.length > 0
      ? `Selected theory basis:\n- ${selectedTheoryRefs.join("\n- ")}`
      : "",
    "Treat the governed manifest and active task packet as authoritative.",
  ]
    .filter(Boolean)
    .join("\n\n")
}

async function executeCodingModelRun(
  record: BackendRunRecord,
  options: ExecuteRunOptions,
  accumulator: ExecutionAccumulator,
  manifest: TaskPacketManifest | undefined,
  _onCommand: (command: CommandExecution) => void,
): Promise<void> {
  const workspaceRoot = record.request.workspace.worktree_path
  const engine = createRuntimeEngine(options.cfg)
  const packet = manifest?.active_task_packet
  if (!packet) {
    throw new Error("coding_model requires an active governed task packet.")
  }
  const prompt = buildImplementationTask(record.request, manifest)
  const result = await engine.runGovernedEngineering({
    selectedExecutor: "coding_model",
    title: String(packet.objective ?? record.request.plan.objective),
    prompt,
    systemPrompt: buildCodingSystemPrompt(workspaceRoot),
    workspaceRoot,
    claw: {
      workspaceRoot,
      objective: String(packet.objective ?? record.request.plan.objective),
      scope:
        packet.context_summary ??
        packet.code_guidance?.target_paths?.join(", ") ??
        record.request.plan.objective,
      repo: record.request.workspace.canonical_repo_path,
      branchPolicy: `${record.request.workspace.branch_name} on ${record.request.workspace.base_branch}`,
      acceptanceTests:
        record.request.plan.verification_blocks.length > 0
          ? record.request.plan.verification_blocks.map((block) => block.command)
          : record.request.plan.verification_plan,
      commitPolicy: "leave changes ready for deterministic verification",
      reportingContract:
        "Persist execution through Claw manifest/output files and summarize changed files only.",
      escalationPolicy:
        "Stop on destructive ambiguity, trust issues, or broken transport and surface blockers in the manifest.",
      prompt,
      agentName: `devplane-${record.request.task_id}`,
    },
  })
  accumulator.artifacts.push(...(result.artifacts ?? []))
  await writeExecutorSummaryArtifact(
    workspaceRoot,
    "coding-model-output.md",
    "# Coding Model Output\n\n" +
      (result.output || "(no executor output)\n"),
    accumulator,
    {
      name: "coding-model-output",
      kind: "run_summary",
      description: "Packet-scoped coding-model output for the strict engineering run.",
    },
  )
}

async function executeLegacyImplementationRun(
  record: BackendRunRecord,
  options: ExecuteRunOptions,
  accumulator: ExecutionAccumulator,
  onCommand: (command: CommandExecution) => void,
): Promise<void> {
  const workspaceRoot = record.request.workspace.worktree_path
  const tools = createWorkspaceTools(workspaceRoot, { onCommand })
  const engine = createRuntimeEngine(options.cfg)
  const taskDescription = [
    `Objective: ${record.request.plan.objective}`,
    record.request.plan.constraints.length > 0
      ? `Constraints:\n- ${record.request.plan.constraints.join("\n- ")}`
      : "",
    record.request.plan.acceptance_criteria.length > 0
      ? `Acceptance criteria:\n- ${record.request.plan.acceptance_criteria.join("\n- ")}`
      : "",
    record.request.plan.implementation_outline.length > 0
      ? `Implementation outline:\n- ${record.request.plan.implementation_outline.join("\n- ")}`
      : "",
    "Legacy dev-plane run: no governed packet is present, so use the plan as the primary execution contract.",
    "Use workspace_git_status before and after meaningful edits.",
  ]
    .filter(Boolean)
    .join("\n\n")
  const result = await engine.runGovernedTaskGraph({
    teamName: `devplane-${record.request.task_id}-legacy`,
    extraTools: tools,
    tasks: [
      {
        title: "Implement requested changes",
        description: taskDescription,
        assignee: "implementation_executor",
        systemPrompt: buildCodingSystemPrompt(workspaceRoot),
        toolNames: tools.map((tool) => tool.name),
        maxTurns: 10,
      },
    ],
  })
  await writeExecutorSummaryArtifact(
    workspaceRoot,
    "legacy-agent-platform-output.md",
    "# Legacy Agent Platform Output\n\n" +
      (result.output || "(no executor output)\n"),
    accumulator,
    {
      name: "legacy-agent-platform-output",
      kind: "run_summary",
      description: "Legacy single-executor output for non-governed dev-plane runs.",
    },
  )
}

async function executeLocalGeneralRun(
  record: BackendRunRecord,
  options: ExecuteRunOptions,
  accumulator: ExecutionAccumulator,
  manifest: TaskPacketManifest | undefined,
  onCommand: (command: CommandExecution) => void,
): Promise<void> {
  const workspaceRoot = record.request.workspace.worktree_path
  const allTools = createWorkspaceTools(workspaceRoot, { onCommand })
  const allowedTools = allTools.filter((tool) =>
    ["workspace_find_files", "workspace_file_read", "workspace_git_status"].includes(tool.name),
  )
  const engine = createRuntimeEngine(options.cfg)
  const result = await engine.runGovernedEngineering({
    selectedExecutor: "local_general_model",
    title: "Summarize governed engineering state",
    prompt: buildReadOnlyTask("Summarize governed engineering state", manifest),
    systemPrompt: buildLocalGeneralSystemPrompt(workspaceRoot),
    extraTools: allowedTools,
    toolNames: allowedTools.map((tool) => tool.name),
  })
  await writeExecutorSummaryArtifact(
    workspaceRoot,
    "local-general-output.md",
    "# Local General Model Output\n\n" +
      (result.output || "(no executor output)\n"),
    accumulator,
    {
      name: "local-general-output",
      kind: "run_summary",
      description: "Read-only local general model output for the strict engineering run.",
    },
  )
}

async function executeMultimodalRun(
  record: BackendRunRecord,
  options: ExecuteRunOptions,
  accumulator: ExecutionAccumulator,
  manifest: TaskPacketManifest | undefined,
): Promise<void> {
  if (!options.cfg.modelRuntimeBaseUrl) {
    throw new Error("multimodal_model requires MODEL_RUNTIME_URL for strict engineering runs.")
  }
  const packet = manifest?.active_task_packet
  if (!packet) {
    throw new Error("multimodal_model requires an active governed task packet.")
  }
  const engine = createRuntimeEngine(options.cfg)
  const response = await engine.runGovernedEngineering({
    selectedExecutor: "multimodal_model",
    title: "Extract multimodal structured output",
    prompt: buildReadOnlyTask("Extract multimodal structured output", manifest),
    systemPrompt:
      "You are dispatching a governed multimodal extraction task. Return only packet-scoped structured output.",
    packet: packet as unknown as Record<string, unknown>,
  })
  const workspaceRoot = record.request.workspace.worktree_path
  const outputPath = path.join(workspaceRoot, ".birtha", "multimodal-output.json")
  await mkdir(path.dirname(outputPath), { recursive: true })
  await writeFile(
    outputPath,
    JSON.stringify(
      {
        selected_executor: "multimodal_model",
        task_packet_ref: manifest?.active_task_packet_ref,
        model_id_resolved: response.model,
        usage: response.usage,
        structured_output: response.structuredOutput ?? {},
        text: response.output ?? "",
      },
      null,
      2,
    ),
    "utf8",
  )
  accumulator.artifacts.push({
    name: "multimodal-output",
    path: outputPath,
    kind: "run_summary",
    description: "Structured multimodal output for the strict engineering run.",
  })
}

async function executeValidatorNoop(
  record: BackendRunRecord,
  accumulator: ExecutionAccumulator,
  manifest: TaskPacketManifest | undefined,
): Promise<void> {
  const workspaceRoot = record.request.workspace.worktree_path
  await writeExecutorSummaryArtifact(
    workspaceRoot,
    "validator-dispatch.md",
    [
      "# Deterministic Validator Dispatch",
      "",
      "Implementation phase skipped because the active governed packet is routed to `deterministic_validator`.",
      manifest?.active_task_packet_ref ? `Task packet: ${manifest.active_task_packet_ref}` : "",
    ]
      .filter(Boolean)
      .join("\n"),
    accumulator,
    {
      name: "validator-dispatch",
      kind: "run_summary",
      description: "Marker artifact showing validator-routed packet dispatch.",
    },
  )
}

async function executeStrategicReviewerRun(
  record: BackendRunRecord,
  options: ExecuteRunOptions,
  accumulator: ExecutionAccumulator,
  manifest: TaskPacketManifest | undefined,
  onCommand: (command: CommandExecution) => void,
): Promise<void> {
  if (!manifest?.escalation_packets || manifest.escalation_packets.length === 0) {
    throw new Error("strategic_reviewer requires a typed escalation packet in the manifest.")
  }
  const workspaceRoot = record.request.workspace.worktree_path
  const allTools = createWorkspaceTools(workspaceRoot, { onCommand })
  const allowedTools = allTools.filter((tool) =>
    ["workspace_find_files", "workspace_file_read", "workspace_git_status"].includes(tool.name),
  )
  const engine = createRuntimeEngine(options.cfg)
  const result = await engine.runGovernedEngineering({
    selectedExecutor: "strategic_reviewer",
    title: "Review typed escalation packet",
    prompt: buildReadOnlyTask("Review typed escalation packet", manifest),
    systemPrompt: buildStrategicReviewSystemPrompt(workspaceRoot),
    extraTools: allowedTools,
    toolNames: allowedTools.map((tool) => tool.name),
  })
  await writeExecutorSummaryArtifact(
    workspaceRoot,
    "strategic-review-output.md",
    "# Strategic Review Output\n\n" +
      (result.output || "(no reviewer output)\n"),
    accumulator,
    {
      name: "strategic-review-output",
      kind: "run_summary",
      description: "Strategic review output for a typed engineering escalation.",
    },
  )
}

async function writeExecutorSummaryArtifact(
  workspaceRoot: string,
  filename: string,
  content: string,
  accumulator: ExecutionAccumulator,
  artifact: Pick<ArtifactRecord, "name" | "kind" | "description">,
): Promise<void> {
  const outputPath = path.join(workspaceRoot, ".birtha", filename)
  await mkdir(path.dirname(outputPath), { recursive: true })
  await writeFile(outputPath, content, "utf8")
  accumulator.artifacts.push({
    ...artifact,
    path: outputPath,
  })
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
