import { readdir, readFile } from "node:fs/promises"
import path from "node:path"
import { describe, expect, it } from "vitest"
import type { PlatformConfig } from "../config.js"
import { LLMManager } from "../llm/manager.js"
import { OrchestrationEngine } from "./engine.js"

function baseConfig(): PlatformConfig {
  return {
    ragUrl: "http://rag",
    asrUrl: "http://asr",
    mcpUrl: "http://mcp",
    toolRegistryUrl: "http://tools",
    llmRunnerUrl: "http://llm:8000",
    llmRunnerApiKey: undefined,
    llmBackend: "mock",
    ollamaModel: "ollama-model",
    vllmModel: "vllm-model",
    huggingfaceModel: "hf-model",
    huggingfaceBaseUrl: "https://router.huggingface.co/v1",
    huggingfaceApiKey: undefined,
    apiBrainEnabled: false,
    apiBrainMaxEscalationsPerTask: 1,
    apiBrainProvider: "openai",
    apiBrainModel: "",
    orchestrationDefaultModel: "default-model",
    orchestrationDefaultProvider: "anthropic",
    orchestrationDefaultBaseUrl: undefined,
    orchestrationDefaultApiKey: undefined,
    orchestrationMaxTokenBudget: 1234,
    orchestratorApiUrl: "",
    modelRuntimeBaseUrl: "",
    clawCodeBinary: "claw",
    clawCodeModel: undefined,
    clawCodeTrustedRoots: [],
    clawCodePollIntervalMs: 100,
    clawCodeTimeoutMs: 1000,
    clawCodeMaxConcurrentLanes: 1,
  }
}

async function collectFiles(root: string): Promise<string[]> {
  const entries = await readdir(root, { withFileTypes: true })
  const files = await Promise.all(
    entries.map(async (entry) => {
      const fullPath = path.join(root, entry.name)
      if (entry.isDirectory()) {
        return collectFiles(fullPath)
      }
      return fullPath
    }),
  )
  return files.flat()
}

describe("orchestration boundaries", () => {
  it("donor package does not import Claw internals", async () => {
    const donorSrc = path.resolve(
      process.cwd(),
      "../../../merged claude leak/packages/open-multi-agent/src",
    )
    const files = (await collectFiles(donorSrc)).filter((file) => file.endsWith(".ts"))
    for (const file of files) {
      const source = await readFile(file, "utf8")
      const importSpecifiers = [
        ...source.matchAll(/from\s+["']([^"']+)["']/g),
        ...source.matchAll(/import\(\s*["']([^"']+)["']\s*\)/g),
      ].map((match) => match[1] ?? "")
      for (const specifier of importSpecifiers) {
        expect(specifier, `${file} unexpectedly imports ${specifier}`).not.toMatch(/claw/i)
      }
    }
  })

  it("the Claw adapter remains translation-only and does not own orchestration policy", async () => {
    const adapterPath = path.resolve(process.cwd(), "src/orchestration/claw-code-executor.ts")
    const source = await readFile(adapterPath, "utf8")
    expect(source).not.toMatch(/resolveExecutorRuntime/)
    expect(source).not.toMatch(/resolveMergedOmaRoute/)
    expect(source).not.toMatch(/OpenMultiAgent/)
    expect(source).not.toMatch(/runTeam\(/)
    expect(source).not.toMatch(/runTasks\(/)
    expect(source).not.toMatch(/selectedExecutor/)
  })

  it("coding_model requires the Claw boundary and never falls back to donor task execution", async () => {
    const cfg = baseConfig()
    const engine = new OrchestrationEngine(cfg, new LLMManager(cfg))
    await expect(
      engine.runGovernedEngineering({
        selectedExecutor: "coding_model",
        title: "Implement change",
        prompt: "Implement the requested change.",
        systemPrompt: "You are the governed coding executor.",
      }),
    ).rejects.toThrow("workspaceRoot")
    await expect(
      engine.runGovernedEngineering({
        selectedExecutor: "coding_model",
        title: "Implement change",
        prompt: "Implement the requested change.",
        systemPrompt: "You are the governed coding executor.",
        workspaceRoot: "/tmp/governed-workspace",
      }),
    ).rejects.toThrow("translated Claw execution input")
  })
})
