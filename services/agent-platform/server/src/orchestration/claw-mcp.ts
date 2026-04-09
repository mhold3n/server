import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process"

interface JsonRpcError {
  code: number
  message: string
  data?: unknown
}

interface JsonRpcResponse<T = unknown> {
  jsonrpc: "2.0"
  id?: number | string | null
  result?: T
  error?: JsonRpcError
}

interface McpInitializeResult {
  protocolVersion: string
  capabilities?: Record<string, unknown>
  serverInfo?: {
    name?: string
    version?: string
  }
}

export interface McpToolCallResult {
  content?: Array<{
    type?: string
    text?: string
    [key: string]: unknown
  }>
  structuredContent?: unknown
  isError?: boolean
}

function frame(payload: unknown): Buffer {
  const body = Buffer.from(JSON.stringify(payload), "utf8")
  return Buffer.concat([Buffer.from(`Content-Length: ${body.length}\r\n\r\n`, "utf8"), body])
}

export class ClawMcpClient {
  private child: ChildProcessWithoutNullStreams | undefined
  private readonly pending = new Map<
    number,
    {
      resolve: (value: unknown) => void
      reject: (error: Error) => void
      timer: NodeJS.Timeout
    }
  >()
  private readonly stderr: string[] = []
  private buffer = Buffer.alloc(0)
  private nextId = 1
  private closed = false

  private constructor(
    private readonly binary: string,
    private readonly cwd: string,
    private readonly env: NodeJS.ProcessEnv,
    private readonly timeoutMs: number,
  ) {}

  static async start(options: {
    binary: string
    cwd: string
    env?: NodeJS.ProcessEnv
    timeoutMs: number
  }): Promise<ClawMcpClient> {
    const client = new ClawMcpClient(
      options.binary,
      options.cwd,
      options.env ?? process.env,
      options.timeoutMs,
    )
    await client.open()
    return client
  }

  getStderr(): string {
    return this.stderr.join("")
  }

  async listTools(): Promise<unknown> {
    return this.request("tools/list", {})
  }

  async callTool(name: string, args?: Record<string, unknown>): Promise<McpToolCallResult> {
    const result = (await this.request("tools/call", {
      name,
      arguments: args ?? {},
    })) as McpToolCallResult
    if (result.isError) {
      throw new Error(`Claw MCP tool ${name} returned isError=true`)
    }
    return result
  }

  async close(): Promise<void> {
    if (!this.child || this.closed) return
    this.closed = true
    for (const { timer, reject } of this.pending.values()) {
      clearTimeout(timer)
      reject(new Error("Claw MCP client closed"))
    }
    this.pending.clear()
    this.child.kill("SIGTERM")
    await new Promise<void>((resolve) => {
      this.child?.once("exit", () => resolve())
      setTimeout(resolve, 500)
    })
    this.child = undefined
  }

  private async open(): Promise<void> {
    this.child = spawn(this.binary, ["mcp", "serve"], {
      cwd: this.cwd,
      env: this.env,
      stdio: ["pipe", "pipe", "pipe"],
    })
    this.child.stdout.on("data", (chunk: Buffer) => this.onData(chunk))
    this.child.stderr.on("data", (chunk: Buffer) => {
      this.stderr.push(chunk.toString("utf8"))
    })
    this.child.once("error", (error) => this.failAll(error))
    this.child.once("exit", (code, signal) => {
      this.failAll(new Error(`Claw MCP exited before completion (code=${code}, signal=${signal})`))
    })

    await this.initialize()
  }

  private async initialize(): Promise<void> {
    await this.request<McpInitializeResult>("initialize", {
      protocolVersion: "2025-03-26",
      capabilities: {},
      clientInfo: {
        name: "agent-platform",
        version: "0.1.0",
      },
    })
    await this.notify("notifications/initialized", {})
  }

  private async notify(method: string, params?: Record<string, unknown>): Promise<void> {
    if (!this.child) {
      throw new Error("Claw MCP process is not running")
    }
    this.child.stdin.write(frame({ jsonrpc: "2.0", method, params }))
  }

  private async request<T = unknown>(
    method: string,
    params?: Record<string, unknown>,
  ): Promise<T> {
    if (!this.child) {
      throw new Error("Claw MCP process is not running")
    }
    const id = this.nextId++
    const response = new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id)
        reject(new Error(`Timed out waiting for Claw MCP response to ${method}`))
      }, this.timeoutMs)
      this.pending.set(id, { resolve: resolve as (value: unknown) => void, reject, timer })
    })
    this.child.stdin.write(frame({ jsonrpc: "2.0", id, method, params }))
    return response
  }

  private onData(chunk: Buffer): void {
    this.buffer = Buffer.concat([this.buffer, chunk])
    while (true) {
      const headerEnd = this.buffer.indexOf("\r\n\r\n")
      if (headerEnd === -1) return

      const header = this.buffer.slice(0, headerEnd).toString("utf8")
      const match = header.match(/content-length:\s*(\d+)/i)
      if (!match) {
        this.failAll(new Error("Claw MCP response missing Content-Length header"))
        return
      }

      const contentLength = Number(match[1])
      const frameStart = headerEnd + 4
      const frameEnd = frameStart + contentLength
      if (this.buffer.length < frameEnd) return

      const payload = this.buffer.slice(frameStart, frameEnd)
      this.buffer = this.buffer.slice(frameEnd)

      let message: JsonRpcResponse
      try {
        message = JSON.parse(payload.toString("utf8")) as JsonRpcResponse
      } catch (error) {
        this.failAll(
          error instanceof Error ? error : new Error(`Invalid Claw MCP payload: ${String(error)}`),
        )
        return
      }

      if (message.id === undefined || message.id === null || typeof message.id !== "number") {
        continue
      }
      const pending = this.pending.get(message.id)
      if (!pending) {
        continue
      }
      clearTimeout(pending.timer)
      this.pending.delete(message.id)

      if (message.error) {
        pending.reject(
          new Error(`Claw MCP ${message.error.code}: ${message.error.message}`),
        )
        continue
      }

      pending.resolve(message.result)
    }
  }

  private failAll(error: Error): void {
    if (this.closed) return
    this.closed = true
    for (const { timer, reject } of this.pending.values()) {
      clearTimeout(timer)
      reject(error)
    }
    this.pending.clear()
  }
}
