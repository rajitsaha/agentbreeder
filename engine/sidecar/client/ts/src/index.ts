export interface RagSearchOpts {
  indexIds: string[]
  topK?: number
}

export interface RagChunk {
  content: string
  score: number
  metadata: Record<string, unknown>
}

export interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
}

export interface CostEvent {
  agentName: string
  model: string
  inputTokens: number
  outputTokens: number
  cost?: number
}

export interface SpanEvent {
  traceId: string
  spanId: string
  name: string
  startTime: number
  endTime: number
  attributes?: Record<string, unknown>
}

export interface AgentRuntimeConfig {
  name: string
  version: string
  framework: string
}

export class APSClient {
  private readonly url: string
  private readonly apiKey: string

  constructor(opts?: { url?: string; apiKey?: string }) {
    this.url = opts?.url ?? process.env.AGENTBREEDER_URL ?? 'http://agentbreeder-api:8000'
    this.apiKey = opts?.apiKey ?? process.env.AGENTBREEDER_API_KEY ?? ''
  }

  // RAG
  rag = {
    search: (query: string, opts: RagSearchOpts): Promise<RagChunk[]> =>
      this._post<RagChunk[]>('/api/v1/rag/search', { query, ...opts }),
  }

  // Memory
  memory = {
    load: (threadId: string): Promise<Message[]> =>
      this._get<Message[]>(`/api/v1/memory/thread/${threadId}`),
    save: (threadId: string, messages: Message[]): Promise<void> =>
      this._post<void>('/api/v1/memory/thread', { thread_id: threadId, messages }),
  }

  // Cost — fire-and-forget, never throws, no retries
  cost = {
    record: (e: CostEvent): void => {
      void this._postOnce('/api/v1/costs/record', e).catch(() => {})
    },
  }

  // Trace — fire-and-forget, never throws, no retries
  trace = {
    span: (e: SpanEvent): void => {
      void this._postOnce('/api/v1/tracing/spans', e).catch(() => {})
    },
  }

  // A2A
  a2a = {
    call: (agentName: string, input: unknown): Promise<unknown> =>
      this._post<unknown>(`/api/v1/a2a/agents/${agentName}/invoke`, { input }),
  }

  // Tool execution
  tools = {
    execute: (name: string, input: unknown): Promise<unknown> =>
      this._post<unknown>('/api/v1/tools/sandbox/execute', { name, input }),
  }

  // Agent runtime config
  config = {
    get: (): Promise<AgentRuntimeConfig> =>
      this._get<AgentRuntimeConfig>('/api/v1/agents/runtime-config'),
  }

  private async _get<T>(path: string): Promise<T> {
    return this._request<T>('GET', path)
  }

  private async _post<T>(path: string, body: unknown): Promise<T> {
    return this._request<T>('POST', path, body)
  }

  /** Single-attempt POST — used for fire-and-forget telemetry paths (no retries). */
  private async _postOnce<T>(path: string, body: unknown): Promise<T> {
    const url = `${this.url}${path}`
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${this.apiKey}`,
    }
    const res = await fetch(url, { method: 'POST', headers, body: JSON.stringify(body) })
    if (res.status === 204) return undefined as T
    if (res.ok) return res.json() as Promise<T>
    throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  }

  private async _request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const url = `${this.url}${path}`
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${this.apiKey}`,
    }
    const init: RequestInit = { method, headers }
    if (body !== undefined) {
      init.body = JSON.stringify(body)
    }

    let lastError: unknown
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const res = await fetch(url, init)
        if (res.ok) {
          // For void responses (204 No Content)
          if (res.status === 204) return undefined as T
          return res.json() as Promise<T>
        }
        if (res.status >= 500) {
          lastError = new Error(`HTTP ${res.status}: ${await res.text()}`)
          if (attempt < 2) {
            await new Promise(r => setTimeout(r, 500 * 2 ** attempt))
            continue
          }
        } else {
          throw new Error(`HTTP ${res.status}: ${await res.text()}`)
        }
      } catch (err) {
        lastError = err
        if (attempt < 2) {
          await new Promise(r => setTimeout(r, 500 * 2 ** attempt))
          continue
        }
      }
    }
    throw lastError
  }
}
