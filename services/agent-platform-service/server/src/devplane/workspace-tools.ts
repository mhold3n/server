import { spawn } from "node:child_process"
import { mkdtemp, mkdir, readFile, readdir, writeFile } from "node:fs/promises"
import os from "node:os"
import path from "node:path"
import { z } from "zod"
import { defineTool, type ToolDefinition } from "@server/open-multi-agent"
import type { CommandExecution } from "./types.js"

const DEFAULT_TIMEOUT_MS = 30_000
const MAX_OUTPUT_CHARS = 8_000

export interface WorkspaceToolHooks {
  onCommand?: (command: CommandExecution) => void
}

export function resolveWorkspacePath(
  workspaceRoot: string,
  candidatePath: string,
): string {
  const resolved = path.resolve(
    workspaceRoot,
    candidatePath.startsWith(path.sep)
      ? path.relative(workspaceRoot, candidatePath)
      : candidatePath,
  )
  const normalizedWorkspace = path.resolve(workspaceRoot)
  if (
    resolved !== normalizedWorkspace &&
    !resolved.startsWith(`${normalizedWorkspace}${path.sep}`)
  ) {
    throw new Error(`Path "${candidatePath}" escapes the workspace root.`)
  }
  return resolved
}

export function createWorkspaceTools(
  workspaceRoot: string,
  hooks: WorkspaceToolHooks = {},
): ToolDefinition[] {
  const normalizedWorkspace = path.resolve(workspaceRoot)

  const workspaceFileRead = defineTool({
    name: "workspace_file_read",
    description:
      "Read a file inside the assigned task workspace. Paths may be relative to the workspace root.",
    inputSchema: z.object({
      path: z.string(),
      offset: z.number().int().positive().optional(),
      limit: z.number().int().positive().optional(),
    }),
    execute: async (input) => {
      const target = resolveWorkspacePath(normalizedWorkspace, input.path)
      const raw = await readFile(target, "utf8")
      const lines = raw.split("\n")
      if (lines.length > 0 && lines[lines.length - 1] === "") {
        lines.pop()
      }
      const startIndex = input.offset !== undefined ? Math.max(0, input.offset - 1) : 0
      const endIndex =
        input.limit !== undefined
          ? Math.min(lines.length, startIndex + input.limit)
          : lines.length
      const numbered = lines
        .slice(startIndex, endIndex)
        .map((line, index) => `${startIndex + index + 1}\t${line}`)
        .join("\n")
      return { data: numbered || "(file is empty)", isError: false }
    },
  })

  const workspaceFileWrite = defineTool({
    name: "workspace_file_write",
    description:
      "Create or overwrite a file inside the assigned task workspace. Paths may be relative to the workspace root.",
    inputSchema: z.object({
      path: z.string(),
      content: z.string(),
    }),
    execute: async (input) => {
      const target = resolveWorkspacePath(normalizedWorkspace, input.path)
      await mkdir(path.dirname(target), { recursive: true })
      await writeFile(target, input.content, "utf8")
      return {
        data: `Wrote ${path.relative(normalizedWorkspace, target) || path.basename(target)}.`,
        isError: false,
      }
    },
  })

  const workspaceFileEdit = defineTool({
    name: "workspace_file_edit",
    description:
      "Replace an exact string inside a file in the assigned task workspace.",
    inputSchema: z.object({
      path: z.string(),
      old_string: z.string(),
      new_string: z.string(),
      replace_all: z.boolean().optional(),
    }),
    execute: async (input) => {
      const target = resolveWorkspacePath(normalizedWorkspace, input.path)
      const original = await readFile(target, "utf8")
      const count = countOccurrences(original, input.old_string)
      if (count === 0) {
        return {
          data: `Exact string not found in ${path.relative(normalizedWorkspace, target)}.`,
          isError: true,
        }
      }
      if (count > 1 && input.replace_all !== true) {
        return {
          data: `String appears ${count} times; provide a more specific match or set replace_all.`,
          isError: true,
        }
      }
      const updated =
        input.replace_all === true
          ? original.split(input.old_string).join(input.new_string)
          : original.replace(input.old_string, input.new_string)
      await writeFile(target, updated, "utf8")
      return {
        data: `Updated ${path.relative(normalizedWorkspace, target)}.`,
        isError: false,
      }
    },
  })

  const workspaceFindFiles = defineTool({
    name: "workspace_find_files",
    description:
      "List files inside the assigned task workspace matching a substring or regular expression.",
    inputSchema: z.object({
      pattern: z.string(),
      path: z.string().optional(),
      regex: z.boolean().optional(),
    }),
    execute: async (input) => {
      const root = resolveWorkspacePath(normalizedWorkspace, input.path ?? ".")
      const matcher =
        input.regex === true
          ? new RegExp(input.pattern)
          : null
      const results: string[] = []
      for await (const entry of walkFiles(root)) {
        const rel = path.relative(normalizedWorkspace, entry) || path.basename(entry)
        if (matcher ? matcher.test(rel) : rel.includes(input.pattern)) {
          results.push(rel)
        }
      }
      return {
        data: results.length > 0 ? results.join("\n") : "(no matching files)",
        isError: false,
      }
    },
  })

  const workspaceGitStatus = defineTool({
    name: "workspace_git_status",
    description:
      "Return `git status --short` for the assigned task workspace.",
    inputSchema: z.object({}),
    execute: async () => {
      const command = await runCommand("git status --short", {
        cwd: normalizedWorkspace,
        workspaceRoot: normalizedWorkspace,
        timeoutMs: DEFAULT_TIMEOUT_MS,
      })
      hooks.onCommand?.(command)
      return {
        data: formatCommandOutput(command),
        isError: (command.exit_code ?? 1) !== 0,
      }
    },
  })

  const workspaceBash = defineTool({
    name: "workspace_bash",
    description:
      "Run a shell command inside the assigned task workspace. This tool rejects commands that target paths outside the workspace or attempt publish/network control operations.",
    inputSchema: z.object({
      command: z.string(),
      cwd: z.string().optional(),
      timeout: z.number().int().positive().optional(),
    }),
    execute: async (input) => {
      const cwd = resolveWorkspacePath(normalizedWorkspace, input.cwd ?? ".")
      const command = await runCommand(input.command, {
        cwd,
        workspaceRoot: normalizedWorkspace,
        timeoutMs: input.timeout ?? DEFAULT_TIMEOUT_MS,
      })
      hooks.onCommand?.(command)
      return {
        data: formatCommandOutput(command),
        isError: (command.exit_code ?? 1) !== 0,
      }
    },
  })

  return [
    workspaceFileRead,
    workspaceFileWrite,
    workspaceFileEdit,
    workspaceFindFiles,
    workspaceGitStatus,
    workspaceBash,
  ]
}

async function runCommand(
  command: string,
  options: {
    cwd: string
    workspaceRoot: string
    timeoutMs: number
  },
): Promise<CommandExecution> {
  assertCommandIsSafe(command, options.workspaceRoot)

  const tempHome = await mkdtemp(path.join(os.tmpdir(), "birtha-devplane-home-"))
  const env = {
    ...process.env,
    HOME: tempHome,
  }

  const result = await new Promise<{
    stdout: string
    stderr: string
    exitCode: number
  }>((resolve) => {
    const stdoutChunks: Buffer[] = []
    const stderrChunks: Buffer[] = []
    const child = spawn("bash", ["-lc", command], {
      cwd: options.cwd,
      env,
      stdio: ["ignore", "pipe", "pipe"],
    })
    child.stdout.on("data", (chunk: Buffer) => stdoutChunks.push(chunk))
    child.stderr.on("data", (chunk: Buffer) => stderrChunks.push(chunk))

    let settled = false
    let timedOut = false
    const timer = setTimeout(() => {
      timedOut = true
      child.kill("SIGKILL")
    }, options.timeoutMs)

    const done = (exitCode: number) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      resolve({
        stdout: Buffer.concat(stdoutChunks).toString("utf8"),
        stderr: Buffer.concat(stderrChunks).toString("utf8"),
        exitCode,
      })
    }

    child.on("close", (code) => {
      done(code ?? (timedOut ? 124 : 1))
    })
    child.on("error", (error) => {
      done(error.message ? 127 : 1)
    })
  })

  return {
    command,
    cwd: options.cwd,
    exit_code: result.exitCode,
    stdout_excerpt: truncate(result.stdout),
    stderr_excerpt: truncate(result.stderr),
    source: "agent-platform",
  }
}

function formatCommandOutput(command: CommandExecution): string {
  const parts: string[] = []
  if (command.stdout_excerpt) {
    parts.push(command.stdout_excerpt)
  }
  if (command.stderr_excerpt) {
    parts.push(
      parts.length > 0
        ? `--- stderr ---\n${command.stderr_excerpt}`
        : command.stderr_excerpt,
    )
  }
  if (parts.length === 0) {
    return command.exit_code === 0
      ? "(command completed with no output)"
      : `(command exited with code ${command.exit_code ?? 1}, no output)`
  }
  if ((command.exit_code ?? 0) !== 0) {
    parts.push(`\n(exit code: ${command.exit_code ?? 1})`)
  }
  return parts.join("\n")
}

function assertCommandIsSafe(command: string, workspaceRoot: string): void {
  const trimmed = command.trim()
  const blockedFragments = [
    "git push",
    "git remote",
    "git worktree",
    "gh ",
    "ssh ",
    "scp ",
    "sudo ",
    "curl ",
    "wget ",
    "rm -rf /",
    "rm -rf ..",
    "cd /",
    "cd ..",
  ]
  if (blockedFragments.some((fragment) => trimmed.includes(fragment))) {
    throw new Error(`Blocked unsafe shell command: ${command}`)
  }
  const pathMatches = command.match(/(?:^|[\s'"])(\/[^\s'"]+)/g) ?? []
  for (const rawMatch of pathMatches) {
    const candidate = rawMatch.trim().replace(/^['"]|['"]$/g, "")
    if (candidate.startsWith("http://") || candidate.startsWith("https://")) {
      continue
    }
    const resolved = path.resolve(candidate)
    const normalizedWorkspace = path.resolve(workspaceRoot)
    if (
      resolved !== normalizedWorkspace &&
      !resolved.startsWith(`${normalizedWorkspace}${path.sep}`)
    ) {
      throw new Error(`Command references path outside workspace: ${candidate}`)
    }
  }
}

async function* walkFiles(root: string): AsyncGenerator<string> {
  const entries = await readdir(root, { withFileTypes: true })
  for (const entry of entries) {
    if (entry.name === ".git" || entry.name === "node_modules") {
      continue
    }
    const nextPath = path.join(root, entry.name)
    if (entry.isDirectory()) {
      yield* walkFiles(nextPath)
    } else if (entry.isFile()) {
      yield nextPath
    }
  }
}

function countOccurrences(haystack: string, needle: string): number {
  if (needle.length === 0) return 0
  let count = 0
  let start = 0
  while (true) {
    const index = haystack.indexOf(needle, start)
    if (index === -1) break
    count += 1
    start = index + needle.length
  }
  return count
}

function truncate(value: string): string | undefined {
  if (value.length === 0) return undefined
  if (value.length <= MAX_OUTPUT_CHARS) {
    return value
  }
  return `${value.slice(0, MAX_OUTPUT_CHARS)}\n...<truncated>`
}
