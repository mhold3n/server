import { mkdtemp, rm, writeFile } from "node:fs/promises"
import os from "node:os"
import path from "node:path"
import { afterEach, describe, expect, it } from "vitest"
import { createWorkspaceTools, resolveWorkspacePath } from "./workspace-tools.js"

const tempPaths: string[] = []

afterEach(async () => {
  await Promise.all(tempPaths.splice(0).map((entry) => rm(entry, { recursive: true, force: true })))
})

describe("workspace tools", () => {
  it("resolveWorkspacePath rejects escapes outside the workspace", async () => {
    const workspace = await mkdtemp(path.join(os.tmpdir(), "workspace-tools-"))
    tempPaths.push(workspace)
    expect(() => resolveWorkspacePath(workspace, "../outside.txt")).toThrow(
      /escapes the workspace root/i,
    )
  })

  it("workspace_bash blocks publish and external-path commands", async () => {
    const workspace = await mkdtemp(path.join(os.tmpdir(), "workspace-tools-"))
    tempPaths.push(workspace)
    await writeFile(path.join(workspace, "README.md"), "# Example\n", "utf8")
    const tools = createWorkspaceTools(workspace)
    const bashTool = tools.find((tool) => tool.name === "workspace_bash")
    expect(bashTool).toBeDefined()

    await expect(
      bashTool!.execute(
        { command: "git push origin main" },
        { agent: { name: "tester", role: "test", model: "mock" } },
      ),
    ).rejects.toThrow(/blocked unsafe shell command/i)

    await expect(
      bashTool!.execute(
        { command: "cat /etc/hosts" },
        { agent: { name: "tester", role: "test", model: "mock" } },
      ),
    ).rejects.toThrow(/outside workspace/i)
  })
})
