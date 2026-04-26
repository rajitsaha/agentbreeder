import { APSClient, type CostEvent, type SpanEvent, type RagSearchOpts } from '../index.js'
import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals'

let mockFetch: jest.MockedFunction<typeof fetch>

beforeEach(() => {
  mockFetch = jest.fn<typeof fetch>()
  global.fetch = mockFetch as unknown as typeof fetch
  delete process.env.AGENTBREEDER_URL
  delete process.env.AGENTBREEDER_API_KEY
})

afterEach(() => {
  // Replace global fetch with a no-op to absorb any in-flight background retries
  // so they don't bleed into the next test's mock call count
  global.fetch = jest.fn<typeof fetch>().mockResolvedValue({
    ok: false,
    status: 500,
    text: () => Promise.resolve('absorbed'),
  } as Response) as unknown as typeof fetch
})

describe('APSClient', () => {
  it('reads URL and API key from env vars', () => {
    process.env.AGENTBREEDER_URL = 'http://test-api:9000'
    process.env.AGENTBREEDER_API_KEY = 'test-key-123'
    const client = new APSClient()
    // access private fields for test
    expect((client as any).url).toBe('http://test-api:9000')
    expect((client as any).apiKey).toBe('test-key-123')
  })

  it('constructor opts override env vars', () => {
    process.env.AGENTBREEDER_URL = 'http://env-api:9000'
    const client = new APSClient({ url: 'http://override:1234', apiKey: 'override-key' })
    expect((client as any).url).toBe('http://override:1234')
    expect((client as any).apiKey).toBe('override-key')
  })

  it('cost.record() does not throw on 500', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      text: () => Promise.resolve('Internal Server Error'),
    } as Response)
    const client = new APSClient({ url: 'http://localhost:8000' })
    const event: CostEvent = {
      agentName: 'test-agent',
      model: 'claude-sonnet-4-6',
      inputTokens: 100,
      outputTokens: 50,
    }
    // Should NOT throw — cost.record is fire-and-forget
    expect(() => client.cost.record(event)).not.toThrow()
    // Wait a tick to ensure at least the first fetch call was made
    await new Promise(r => setTimeout(r, 10))
    expect(mockFetch).toHaveBeenCalled()
  })

  it('trace.span() does not throw on 500', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      text: () => Promise.resolve('Internal Server Error'),
    } as Response)
    const client = new APSClient({ url: 'http://localhost:8000' })
    const event: SpanEvent = {
      traceId: 'trace-1',
      spanId: 'span-1',
      name: 'agent.invoke',
      startTime: Date.now(),
      endTime: Date.now() + 100,
    }
    // Should NOT throw — trace.span is fire-and-forget
    expect(() => client.trace.span(event)).not.toThrow()
    await new Promise(r => setTimeout(r, 10))
    expect(mockFetch).toHaveBeenCalled()
  })

  it('rag.search() retries 3 times on 5xx then raises', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 503,
      text: () => Promise.resolve('Service Unavailable'),
    } as Response)
    const client = new APSClient({ url: 'http://localhost:8000' })
    const opts: RagSearchOpts = { indexIds: ['idx-1'], topK: 5 }
    await expect(client.rag.search('my query', opts)).rejects.toThrow()
    // 3 attempts total
    expect(mockFetch).toHaveBeenCalledTimes(3)
  }, 30000)
})
