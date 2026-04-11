import { afterEach, describe, expect, it, vi } from 'vitest'
import { chatOpts, collectEvents, textMsg, toolDef, toolResultMsg, toolUseMsg } from './helpers/llm-fixtures.js'
import { OllamaAdapter } from '../src/llm/ollama.js'

function mockFetchResponse(payload: unknown) {
  return vi.fn(async () => new Response(JSON.stringify(payload), { status: 200 }))
}

describe('OllamaAdapter', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('uses native /api/chat without appending /v1', async () => {
    const fetchMock = mockFetchResponse({
      model: 'llama3',
      message: { role: 'assistant', content: 'hello' },
      done_reason: 'stop',
      prompt_eval_count: 3,
      eval_count: 2,
    })
    vi.stubGlobal('fetch', fetchMock)

    const adapter = new OllamaAdapter('ollama-local', 'http://localhost:11434/v1')
    const result = await adapter.chat([textMsg('user', 'hi')], chatOpts({ model: 'llama3' }))

    expect(fetchMock.mock.calls[0]?.[0]).toBe('http://localhost:11434/api/chat')
    expect(result.content).toEqual([{ type: 'text', text: 'hello' }])
    expect(result.stop_reason).toBe('end_turn')
  })

  it('checks native /api/tags health without appending /v1', async () => {
    const fetchMock = mockFetchResponse({
      models: [{ name: 'llama3:8b' }, { model: 'nomic-embed-text' }],
    })
    vi.stubGlobal('fetch', fetchMock)

    const adapter = new OllamaAdapter('ollama-local', 'http://localhost:11434/v1')
    const health = await adapter.health()

    expect(fetchMock.mock.calls[0]?.[0]).toBe('http://localhost:11434/api/tags')
    expect(health).toEqual({
      healthy: true,
      models: ['llama3:8b', 'nomic-embed-text'],
    })
  })

  it('passes tools and preserves native tool calls', async () => {
    const fetchMock = mockFetchResponse({
      model: 'llama3',
      message: {
        role: 'assistant',
        content: '',
        tool_calls: [{ function: { name: 'search', arguments: { query: 'hi' } } }],
      },
      done_reason: 'stop',
      prompt_eval_count: 5,
      eval_count: 1,
    })
    vi.stubGlobal('fetch', fetchMock)

    const adapter = new OllamaAdapter('ollama-local', 'http://localhost:11434')
    const result = await adapter.chat(
      [textMsg('user', 'find it')],
      chatOpts({ model: 'llama3', tools: [toolDef('search', 'Search')] }),
    )
    const body = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))

    expect(body.tools[0].function.name).toBe('search')
    expect(result.stop_reason).toBe('tool_use')
    expect(result.content[0]).toMatchObject({
      type: 'tool_use',
      name: 'search',
      input: { query: 'hi' },
    })
  })

  it('serializes prior tool calls and tool results for the next turn', async () => {
    const fetchMock = mockFetchResponse({
      model: 'llama3',
      message: { role: 'assistant', content: 'done' },
      done_reason: 'stop',
    })
    vi.stubGlobal('fetch', fetchMock)

    const adapter = new OllamaAdapter('ollama-local', 'http://localhost:11434')
    await adapter.chat(
      [
        toolUseMsg('call-1', 'search', { query: 'hi' }),
        toolResultMsg('call-1', 'result'),
      ],
      chatOpts({ model: 'llama3' }),
    )
    const body = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))

    expect(body.messages).toEqual([
      {
        role: 'assistant',
        content: '',
        tool_calls: [{ function: { name: 'search', arguments: { query: 'hi' } } }],
      },
      { role: 'tool', content: 'result' },
    ])
  })

  it('stream produces terminal done event from native chat result', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetchResponse({
        model: 'llama3',
        message: { role: 'assistant', content: 'hello' },
        done_reason: 'stop',
      }),
    )
    const adapter = new OllamaAdapter('ollama-local', 'http://localhost:11434')
    const events = await collectEvents(adapter.stream([textMsg('user', 'hi')], chatOpts()))

    expect(events.map((event) => event.type)).toEqual(['text', 'done'])
  })
})
