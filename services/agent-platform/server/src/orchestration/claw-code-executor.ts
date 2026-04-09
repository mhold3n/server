import { access, mkdir, readFile, writeFile } from "node:fs/promises"
import path from "node:path"
import type { PlatformConfig } from "../config.js"
import { ClawMcpClient, type McpToolCallResult } from "./claw-mcp.js"

export interface OrchestrationArtifact {
  name: string
  path: string
  kind: string
  description?: string
}

export interface ClawCodeExecutionInput {
  workspaceRoot: string
  objective: string
  scope: string
  repo: string
  branchPolicy: string
  acceptanceTests: string[]
  commitPolicy: string
  reportingContract: string
  escalationPolicy: string
  prompt: string
  agentName?: string
  model?: string
}

export interface ClawCodeExecutionResult {
  output: string
  artifacts: OrchestrationArtifact[]
}

interface WorkerStateSnapshot {
  worker_id?: string
  status?: string
  is_ready?: boolean
  trust_gate_cleared?: boolean
  seconds_since_update?: number
}

interface AgentManifest {
  agentId?: string
  status?: string
  outputFile?: string
  manifestFile?: string
  error?: string
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function extractToolPayload<T>(result: McpToolCallResult): T {
  if (result.structuredContent !== undefined) {
    return result.structuredContent as T
  }
  const text = (result.content ?? [])
    .map((part) => (typeof part.text === "string" ? part.text : ""))
    .join("\n")
    .trim()
  if (!text) {
    return {} as T
  }
  try {
    return JSON.parse(text) as T
  } catch {
    return text as T
  }
}

function translatedTaskPacket(input: ClawCodeExecutionInput): Record<string, unknown> {
  return {
    objective: input.objective,
    scope: input.scope,
    repo: input.repo,
    branch_policy: input.branchPolicy,
    acceptance_tests: input.acceptanceTests,
    commit_policy: input.commitPolicy,
    reporting_contract: input.reportingContract,
    escalation_policy: input.escalationPolicy,
  }
}

export class ClawCodeExecutor {
  constructor(private readonly cfg: PlatformConfig) {}

  async execute(input: ClawCodeExecutionInput): Promise<ClawCodeExecutionResult> {
    const clawDir = path.join(input.workspaceRoot, ".birtha", "claw")
    const agentStoreDir = path.join(clawDir, "agents")
    const translatedPacketPath = path.join(clawDir, "translated-task-packet.json")
    const promptPath = path.join(clawDir, "prompt.md")
    const workerStatePath = path.join(input.workspaceRoot, ".claw", "worker-state.json")

    await mkdir(agentStoreDir, { recursive: true })
    await writeFile(
      translatedPacketPath,
      JSON.stringify(translatedTaskPacket(input), null, 2),
      "utf8",
    )
    await writeFile(promptPath, input.prompt, "utf8")

    const env = {
      ...process.env,
      CLAWD_AGENT_STORE: agentStoreDir,
    }

    const client = await ClawMcpClient.start({
      binary: this.cfg.clawCodeBinary,
      cwd: input.workspaceRoot,
      env,
      timeoutMs: this.cfg.clawCodeTimeoutMs,
    })

    try {
      await client.listTools()
      await client.callTool("RunTaskPacket", translatedTaskPacket(input))

      await this.bootstrapWorker(client, input.workspaceRoot, workerStatePath)

      const manifest = extractToolPayload<AgentManifest>(
        await client.callTool("Agent", {
          description: input.objective,
          prompt: input.prompt,
          name: input.agentName ?? "devplane-coding-kernel",
          model: input.model ?? this.cfg.clawCodeModel,
        }),
      )

      if (!manifest.manifestFile || !manifest.outputFile) {
        throw new Error("Claw Agent did not return manifest/output file paths.")
      }

      const completedManifest = await this.waitForAgentManifest(manifest.manifestFile)
      const output = await readFile(manifest.outputFile, "utf8")
      if (completedManifest.status !== "completed") {
        throw new Error(
          `Claw agent failed with status ${completedManifest.status ?? "unknown"}: ${
            completedManifest.error ?? "no error message"
          }`,
        )
      }

      const artifacts: OrchestrationArtifact[] = [
        {
          name: "claw-translated-task-packet",
          path: translatedPacketPath,
          kind: "translated_task_packet",
          description: "Translated DevPlane packet routed into Claw Code.",
        },
        {
          name: "claw-prompt",
          path: promptPath,
          kind: "run_summary",
          description: "Rendered prompt delivered to the external Claw Code kernel.",
        },
        {
          name: "claw-worker-state",
          path: workerStatePath,
          kind: "worker_state",
          description: "Worker lane state emitted by Claw Code during bootstrap.",
        },
        {
          name: "claw-agent-manifest",
          path: manifest.manifestFile,
          kind: "agent_manifest",
          description: "Background agent manifest emitted by Claw Code.",
        },
        {
          name: "claw-agent-output",
          path: manifest.outputFile,
          kind: "agent_output",
          description: "Background agent terminal/output log emitted by Claw Code.",
        },
      ]

      return {
        output,
        artifacts,
      }
    } finally {
      await client.close()
    }
  }

  private async bootstrapWorker(
    client: ClawMcpClient,
    workspaceRoot: string,
    workerStatePath: string,
  ): Promise<void> {
    const trustedRoots =
      this.cfg.clawCodeTrustedRoots.length > 0
        ? this.cfg.clawCodeTrustedRoots
        : [workspaceRoot]

    const created = extractToolPayload<{ worker_id?: string; trust_auto_resolve?: boolean }>(
      await client.callTool("WorkerCreate", {
        cwd: workspaceRoot,
        trusted_roots: trustedRoots,
        auto_recover_prompt_misdelivery: true,
      }),
    )
    const workerId = created.worker_id
    if (!workerId) {
      throw new Error("Claw WorkerCreate did not return a worker_id.")
    }

    if (created.trust_auto_resolve === false) {
      await client.callTool("WorkerObserve", {
        worker_id: workerId,
        screen_text: "Do you trust the files in this folder?",
      })
      const trustState = await this.waitForWorkerState(workerStatePath, (state) =>
        state.status === "trust_required" || state.trust_gate_cleared === true,
      )
      if (trustState.status === "trust_required") {
        await client.callTool("WorkerResolveTrust", { worker_id: workerId })
      }
    }

    await client.callTool("WorkerObserve", {
      worker_id: workerId,
      screen_text: "Ready for input\n>",
    })

    try {
      await this.waitForWorkerState(workerStatePath, (state) => state.is_ready === true)
    } catch {
      await client.callTool("WorkerRestart", { worker_id: workerId })
      await client.callTool("WorkerObserve", {
        worker_id: workerId,
        screen_text: "Ready for input\n>",
      })
      await this.waitForWorkerState(workerStatePath, (state) => state.is_ready === true)
    }
  }

  private async waitForWorkerState(
    workerStatePath: string,
    predicate: (state: WorkerStateSnapshot) => boolean,
  ): Promise<WorkerStateSnapshot> {
    const deadline = Date.now() + this.cfg.clawCodeTimeoutMs
    while (Date.now() < deadline) {
      const state = await this.readJsonIfPresent<WorkerStateSnapshot>(workerStatePath)
      if (state && predicate(state)) {
        return state
      }
      await sleep(this.cfg.clawCodePollIntervalMs)
    }
    throw new Error("Timed out waiting for Claw worker state transition.")
  }

  private async waitForAgentManifest(manifestPath: string): Promise<AgentManifest> {
    const deadline = Date.now() + this.cfg.clawCodeTimeoutMs
    while (Date.now() < deadline) {
      const manifest = await this.readJsonIfPresent<AgentManifest>(manifestPath)
      if (manifest && ["completed", "failed"].includes(String(manifest.status ?? ""))) {
        return manifest
      }
      await sleep(this.cfg.clawCodePollIntervalMs)
    }
    throw new Error("Timed out waiting for Claw agent manifest completion.")
  }

  private async readJsonIfPresent<T>(filePath: string): Promise<T | undefined> {
    try {
      await access(filePath)
      const raw = await readFile(filePath, "utf8")
      return JSON.parse(raw) as T
    } catch {
      return undefined
    }
  }
}
