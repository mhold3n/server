import { Annotation, END, START, StateGraph } from "@langchain/langgraph"
import type { PlatformConfig } from "../config.js"
import { LLMBackendError, LLMManager } from "../llm/manager.js"
import type { ChatMessage } from "../tools/wrkhrs.js"
import {
  extractDomainWeightsFromMessages,
  getDomainData,
  searchKnowledgeBase,
} from "../tools/wrkhrs.js"

const WorkflowAnnotation = Annotation.Root({
  messages: Annotation<ChatMessage[]>(),
  current_step: Annotation<string>(),
  tools_needed: Annotation<string[]>(),
  rag_results: Annotation<string | undefined>(),
  asr_results: Annotation<string | undefined>(),
  tool_results: Annotation<Record<string, string>>({
    reducer: (left, right) => ({ ...left, ...right }),
    default: () => ({}),
  }),
  final_response: Annotation<string | undefined>(),
})

export type WorkflowStateType = typeof WorkflowAnnotation.State

function analyzeRequest(state: WorkflowStateType): Partial<WorkflowStateType> {
  let userMessage = ""
  for (const msg of state.messages) {
    if (msg.role === "user") {
      userMessage = msg.content
      break
    }
  }
  const lower = userMessage.toLowerCase()
  const tools_needed: string[] = []

  if (
    ["what is", "explain", "describe", "how", "why", "definition"].some((k) =>
      lower.includes(k),
    )
  ) {
    tools_needed.push("rag_search")
  }
  if (["audio", "video", "transcript", "speech", "recording"].some((k) => lower.includes(k))) {
    tools_needed.push("asr")
  }
  for (const domain of ["chemistry", "mechanical", "materials"]) {
    if (lower.includes(domain)) {
      tools_needed.push(`mcp_${domain}`)
    }
  }

  return {
    tools_needed,
    current_step: tools_needed.length > 0 ? "gather_context" : "generate_response",
  }
}

function buildGatherContext(cfg: PlatformConfig) {
  return async function gatherContext(
    state: WorkflowStateType,
  ): Promise<Partial<WorkflowStateType>> {
    const messages = state.messages
    let userMessage = ""
    for (const msg of messages) {
      if (msg.role === "user") userMessage = msg.content
    }
    const domainWeights = extractDomainWeightsFromMessages(messages)
    const tool_results: Record<string, string> = { ...state.tool_results }
    let rag_results: string | undefined = state.rag_results
    let asr_results: string | undefined = state.asr_results

    for (const toolName of state.tools_needed) {
      try {
        if (toolName === "rag_search") {
          const result = await searchKnowledgeBase(cfg, userMessage, domainWeights)
          rag_results = result
          tool_results.rag = result
        } else if (toolName === "asr") {
          const result = "Audio processing not implemented in demo"
          asr_results = result
          tool_results.asr = result
        } else if (toolName.startsWith("mcp_")) {
          const domain = toolName.split("_")[1]!
          const result = await getDomainData(cfg, domain, userMessage)
          tool_results[`mcp_${domain}`] = result
        }
      } catch (e) {
        tool_results[toolName] = `Error: ${e instanceof Error ? e.message : String(e)}`
      }
    }

    return {
      rag_results,
      asr_results,
      tool_results,
      current_step: "generate_response",
    }
  }
}

function buildGenerateResponse(llm: LLMManager) {
  return async function generateResponse(
    state: WorkflowStateType,
  ): Promise<Partial<WorkflowStateType>> {
    const contextParts: string[] = []
    if (state.rag_results) {
      contextParts.push(`Knowledge Base Results:\n${state.rag_results}`)
    }
    if (state.asr_results) {
      contextParts.push(`Audio Transcript:\n${state.asr_results}`)
    }
    for (const [toolName, result] of Object.entries(state.tool_results)) {
      if (toolName.startsWith("mcp_")) {
        const domain = toolName.replace("mcp_", "")
        contextParts.push(`${domain.charAt(0).toUpperCase() + domain.slice(1)} Domain Data:\n${result}`)
      }
    }

    let enhancedMessages = [...state.messages]
    if (contextParts.length > 0) {
      const context = contextParts.join("\n\n")
      const sysIdx = enhancedMessages.findIndex((m) => m.role === "system")
      if (sysIdx >= 0) {
        const prev = enhancedMessages[sysIdx]!
        enhancedMessages[sysIdx] = {
          role: "system",
          content: `${prev.content}\n\nAdditional Context:\n${context}`,
        }
      } else {
        enhancedMessages = [{ role: "system", content: `Additional Context:\n${context}` }, ...enhancedMessages]
      }
    }

    try {
      const result = await llm.chatCompletion(enhancedMessages, {
        temperature: 0.7,
        max_tokens: 1000,
      })
      const choices = result.choices
      const content =
        choices[0]?.message?.content ?? "No response generated"
      return {
        final_response: content,
        current_step: "complete",
      }
    } catch (e) {
      const msg =
        e instanceof LLMBackendError
          ? `LLM service error: ${e.message}`
          : `Error generating response: ${e instanceof Error ? e.message : String(e)}`
      return { final_response: msg, current_step: "complete" }
    }
  }
}

export function createChatWorkflow(cfg: PlatformConfig, llm: LLMManager) {
  const gatherContext = buildGatherContext(cfg)
  const generateResponse = buildGenerateResponse(llm)

  const graph = new StateGraph(WorkflowAnnotation)
    .addNode("analyze", analyzeRequest)
    .addNode("gather_context", gatherContext)
    .addNode("generate_response", generateResponse)
    .addEdge(START, "analyze")
    .addConditionalEdges("analyze", (s) =>
      s.tools_needed.length > 0 ? "gather_context" : "generate_response",
    )
    .addEdge("gather_context", "generate_response")
    .addEdge("generate_response", END)

  return graph.compile()
}
