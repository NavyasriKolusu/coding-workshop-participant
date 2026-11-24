import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiRequest, queryString } from './api.js'

describe('apiRequest', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sends the signed token and serializes JSON request bodies', async () => {
    window.localStorage.setItem('acme-token', 'signed-token')
    fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({ id: 1 }),
    })

    await expect(apiRequest('projects', '', {
      method: 'POST',
      body: { name: 'Customer Portal' },
    })).resolves.toEqual({ id: 1 })

    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:3001/api/projects',
      expect.objectContaining({
        method: 'POST',
        headers: {
          'Content-Type': 'application/json; acme-token=signed-token',
          Authorization: 'Bearer signed-token',
        },
        body: JSON.stringify({ name: 'Customer Portal' }),
      }),
    )
  })

  it('clears an expired session and announces unauthorized access', async () => {
    window.localStorage.setItem('acme-token', 'expired-token')
    window.localStorage.setItem('acme-user', '{"role":"member"}')
    fetch.mockResolvedValue({
      ok: false,
      status: 401,
      json: vi.fn().mockResolvedValue({ error: 'Session expired' }),
    })
    const handleUnauthorized = vi.fn()
    window.addEventListener('acme:unauthorized', handleUnauthorized)

    await expect(apiRequest('projects')).rejects.toThrow('Session expired')

    expect(window.localStorage.getItem('acme-token')).toBeNull()
    expect(window.localStorage.getItem('acme-user')).toBeNull()
    expect(handleUnauthorized).toHaveBeenCalledOnce()
    window.removeEventListener('acme:unauthorized', handleUnauthorized)
  })

  it('encodes only non-empty filters', () => {
    expect(queryString({ search: 'Customer Portal', status: '', department: 'Product' }))
      .toBe('?search=Customer+Portal&department=Product')
    expect(queryString({ search: '', status: '' })).toBe('')
  })
})
