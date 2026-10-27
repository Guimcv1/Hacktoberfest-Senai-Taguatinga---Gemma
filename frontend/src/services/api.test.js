import { afterEach, describe, expect, test, vi } from 'vitest'
import { unloadModel } from './api'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('unloadModel', () => {
  test('envia POST autenticado para /api/ai/unload', async () => {
    const fetchMock = vi.fn(async () => new Response(
      JSON.stringify({ status: 'unloaded', model: 'gemma4:e4b', message: 'ok' }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ))
    vi.stubGlobal('fetch', fetchMock)

    const payload = await unloadModel('jwt-token')

    expect(payload.status).toBe('unloaded')
    const [url, options] = fetchMock.mock.calls[0]
    expect(String(url)).toMatch(/\/api\/ai\/unload$/)
    expect(options.method).toBe('POST')
    expect(options.headers.get('Authorization')).toBe('Bearer jwt-token')
  })

  test('propaga a mensagem do backend em 409 e 503', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(
      JSON.stringify({ detail: 'Há uma resposta da IA em andamento. Aguarde terminar antes de descarregar o modelo.' }),
      { status: 409, headers: { 'Content-Type': 'application/json' } },
    )))

    await expect(unloadModel('jwt-token')).rejects.toThrow(/andamento/)
  })
})
