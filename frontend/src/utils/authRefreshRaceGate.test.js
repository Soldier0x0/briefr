import assert from 'node:assert/strict'
import { mock, test } from 'node:test'

/**
 * Gate: AuthContext and api.request must share one in-flight /auth/refresh.
 * A second parallel refresh after rotation trips backend reuse detection and
 * revokes every session — the intermittent BRIEF "Not authenticated" class.
 */

test('refreshAccessToken dedupes concurrent callers onto one /auth/refresh', async () => {
  let refreshCalls = 0
  const originalFetch = globalThis.fetch
  globalThis.fetch = mock.fn(async (url, opts) => {
    const path = typeof url === 'string' ? url : String(url)
    if (path.includes('/auth/refresh')) {
      refreshCalls += 1
      assert.equal(opts?.method, 'POST')
      assert.equal(opts?.credentials, 'include')
      // Hold the first call open so a second caller joins the same promise.
      await new Promise((r) => setTimeout(r, 20))
      return { ok: true, status: 200 }
    }
    throw new Error(`unexpected fetch: ${path}`)
  })

  try {
    // Fresh module instance so module-level refreshPromise starts null.
    const api = await import(`../api.js?refreshRace=${Date.now()}`)
    const [a, b, c] = await Promise.all([
      api.refreshAccessToken(),
      api.refreshAccessToken(),
      api.refreshAccessToken(),
    ])
    assert.equal(a, true)
    assert.equal(b, true)
    assert.equal(c, true)
    assert.equal(refreshCalls, 1, 'concurrent refreshAccessToken must share one HTTP call')
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('AuthContext does not call /auth/refresh with a bare fetch', async () => {
  const { readFileSync } = await import('node:fs')
  const { fileURLToPath } = await import('node:url')
  const { dirname, join } = await import('node:path')
  const here = dirname(fileURLToPath(import.meta.url))
  const src = readFileSync(join(here, '../context/AuthContext.jsx'), 'utf8')
  assert.doesNotMatch(
    src,
    /fetch\(\s*['"`]\/api\/auth\/refresh['"`]/,
    'AuthContext must not call /auth/refresh with a bare fetch',
  )
})
