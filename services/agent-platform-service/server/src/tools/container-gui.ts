import { execFile } from "node:child_process"
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import type { PlatformConfig } from "../config.js"

type JsonObject = Record<string, unknown>
type ContainerGuiToolResult = { data: string; isError?: boolean }

const DEFAULT_REPO_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../../..",
)

function repoRoot(cfg: PlatformConfig): string {
  return cfg.repoRoot ?? process.env.REPO_ROOT ?? DEFAULT_REPO_ROOT
}

function pythonBinary(cfg: PlatformConfig): string {
  const repoPython = path.join(repoRoot(cfg), ".venv", "bin", "python")
  return (
    cfg.knowledgeGuiPython ??
    process.env.KNOWLEDGE_GUI_PYTHON ??
    (fs.existsSync(repoPython) ? repoPython : "python3")
  )
}

async function runPythonScript(
  cfg: PlatformConfig,
  scriptName: string,
  args: string[],
  timeoutMs = 120_000,
): Promise<ContainerGuiToolResult> {
  const cwd = repoRoot(cfg)
  const scriptPath = path.join(cwd, "scripts", scriptName)
  return await new Promise<ContainerGuiToolResult>((resolve) => {
    execFile(
      pythonBinary(cfg),
      [scriptPath, ...args],
      { cwd, timeout: timeoutMs, maxBuffer: 20 * 1024 * 1024 },
      (error, stdout, stderr) => {
        let parsed: unknown = stdout
        try {
          parsed = stdout.trim() ? JSON.parse(stdout) : {}
        } catch {
          parsed = { stdout, stderr }
        }
        const code = typeof (error as { code?: unknown } | null)?.code === "number"
          ? Number((error as { code?: unknown }).code)
          : error
            ? 1
            : 0
        resolve({
          data: JSON.stringify({
            result: parsed,
            stderr,
            returncode: code,
          }),
          isError: Boolean(error),
        })
      },
    )
  })
}

function parseToolData(result: ContainerGuiToolResult): JsonObject {
  try {
    const parsed = JSON.parse(result.data) as unknown
    return parsed && typeof parsed === "object" ? parsed as JsonObject : {}
  } catch {
    return {}
  }
}

function extractOpenClawTargetId(result: ContainerGuiToolResult): string | undefined {
  const outer = parseToolData(result)
  const trace = outer.result
  if (!trace || typeof trace !== "object") return undefined
  const traceResult = (trace as JsonObject).result
  if (!traceResult || typeof traceResult !== "object") return undefined
  const stdout = (traceResult as JsonObject).stdout
  if (typeof stdout !== "string") return undefined
  return stdout.match(/^id:\s*([0-9A-Fa-f]+)\s*$/m)?.[1]
}

export async function launchContainerGui(
  cfg: PlatformConfig,
  input: {
    target_ref: string
    allow_unverified?: boolean
    novnc_port?: number
    artifact_output_dir?: string
  },
): Promise<ContainerGuiToolResult> {
  const args = ["launch", "--target-ref", input.target_ref]
  if (input.allow_unverified) args.push("--allow-unverified")
  if (input.novnc_port !== undefined) args.push("--novnc-port", String(input.novnc_port))
  if (input.artifact_output_dir) args.push("--artifact-output-dir", input.artifact_output_dir)
  return runPythonScript(cfg, "container_gui_session.py", args)
}

export async function resolveContainerGui(
  cfg: PlatformConfig,
  input: { target_ref: string; allow_unverified?: boolean },
): Promise<ContainerGuiToolResult> {
  const args = ["resolve", "--target-ref", input.target_ref]
  if (input.allow_unverified) args.push("--allow-unverified")
  return runPythonScript(cfg, "container_gui_session.py", args)
}

export async function closeContainerGui(
  cfg: PlatformConfig,
  input: { container: string },
): Promise<ContainerGuiToolResult> {
  return runPythonScript(cfg, "container_gui_session.py", ["close", "--container", input.container])
}

export async function listContainerGuiArtifacts(
  cfg: PlatformConfig,
  input: { gui_session_ref: string },
): Promise<ContainerGuiToolResult> {
  return runPythonScript(cfg, "container_gui_session.py", [
    "artifacts",
    "--gui-session-ref",
    input.gui_session_ref,
  ])
}

export async function actOnContainerGui(
  cfg: PlatformConfig,
  input: {
    action: string
    payload?: JsonObject
    trace_path?: string
    dry_run?: boolean
  },
): Promise<ContainerGuiToolResult> {
  const payload = input.payload ?? {}
  const args = [
    "--action",
    input.action,
    "--payload-json",
    JSON.stringify(payload),
  ]
  if (input.trace_path) args.push("--trace-path", input.trace_path)
  if (input.dry_run) args.push("--dry-run")
  return runPythonScript(cfg, "openclaw_container_gui_control.py", args, 60_000)
}

export async function screenshotContainerGui(
  cfg: PlatformConfig,
  input: {
    url?: string
    output?: string
    target_id?: string
    trace_path?: string
    dry_run?: boolean
  },
): Promise<ContainerGuiToolResult> {
  if (input.url) {
    const openResult = await actOnContainerGui(cfg, {
      action: "open",
      payload: { url: input.url },
      trace_path: input.trace_path,
      dry_run: input.dry_run,
    })
    if (openResult.isError) return openResult
  }
  return actOnContainerGui(cfg, {
    action: "screenshot",
    payload: {
      ...(input.output ? { output: input.output } : {}),
      ...(input.target_id ? { target_id: input.target_id } : {}),
    },
    trace_path: input.trace_path,
    dry_run: input.dry_run,
  })
}

export async function recordContainerGui(
  cfg: PlatformConfig,
  input: {
    url?: string
    screenshot_output?: string
    snapshot_output?: string
    trace_path?: string
    dry_run?: boolean
  },
): Promise<ContainerGuiToolResult> {
  const steps: unknown[] = []
  if (input.url) {
    const opened = await actOnContainerGui(cfg, {
      action: "open",
      payload: { url: input.url },
      trace_path: input.trace_path,
      dry_run: input.dry_run,
    })
    steps.push(opened.data)
    if (opened.isError) return { data: JSON.stringify({ steps }), isError: true }
    const targetId = extractOpenClawTargetId(opened)
    if (targetId) {
      const press = await actOnContainerGui(cfg, {
        action: "press",
        payload: { key: "Tab", target_id: targetId },
        trace_path: input.trace_path,
        dry_run: input.dry_run,
      })
      steps.push(press.data)
    }
  }
  const targetId = steps.map((step) => {
    if (typeof step !== "string") return undefined
    return extractOpenClawTargetId({ data: step })
  }).find(Boolean)
  const screenshot = await actOnContainerGui(cfg, {
    action: "screenshot",
    payload: {
      ...(input.screenshot_output ? { output: input.screenshot_output } : {}),
      ...(targetId ? { target_id: targetId } : {}),
    },
    trace_path: input.trace_path,
    dry_run: input.dry_run,
  })
  steps.push(screenshot.data)
  const snapshot = await actOnContainerGui(cfg, {
    action: "snapshot",
    payload: {
      ...(input.snapshot_output ? { output: input.snapshot_output } : {}),
      ...(targetId ? { target_id: targetId } : {}),
    },
    trace_path: input.trace_path,
    dry_run: input.dry_run,
  })
  steps.push(snapshot.data)
  const warnings = screenshot.isError
    ? ["OpenClaw browser screenshot failed; snapshot evidence was still attempted."]
    : []
  return { data: JSON.stringify({ steps, warnings }), isError: snapshot.isError }
}
