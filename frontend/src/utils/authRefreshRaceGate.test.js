import assert from 'node:assert/strict'
import { mock, test } from 'node:test'

/**
 * Gate: AuthContext and api.request must share one in-flight /auth/refresh.
 * A second parallel refresh after rotation trips backend reuse detection and
 * revokes every session — the intermittent BRIEF "Not authenticated" class.
 */

test('refreshAccessToken dedupes concurrent callers onto one /auth/refresh', async () => {
  let meCalls = 0
  let refreshCalls = 0
  const originalFetch = globalThis.fetch
  globalThis.fetch = mock.fn(async (url, opts) => {
    const path = typeof url === 'string' ? url : String(url)
    if (path.includes('/auth/me')) {
      meCalls += 1
      assert.equal(opts?.cache, 'no-store')
      assert.equal(opts?.credentials, 'include')
      return { ok: false, status: 401 }
    }
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
    assert.equal(meCalls, 1, 'session probe must run once per rotation')
    assert.equal(refreshCalls, 1, 'concurrent refreshAccessToken must share one HTTP call')
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('refreshAccessToken skips /auth/refresh when another holder already restored /auth/me', async () => {
  let refreshCalls = 0
  const originalFetch = globalThis.fetch
  globalThis.fetch = mock.fn(async (url) => {
    const path = typeof url === 'string' ? url : String(url)
    if (path.includes('/auth/me')) {
      return { ok: true, status: 200 }
    }
    if (path.includes('/auth/refresh')) {
      refreshCalls += 1
      return { ok: true, status: 200 }
    }
    throw new Error(`unexpected fetch: ${path}`)
  })

  try {
    const api = await import(`../api.js?refreshSkip=${Date.now()}`)
    assert.equal(await api.refreshAccessToken(), true)
    assert.equal(refreshCalls, 0, 'must not rotate when /auth/me already succeeds')
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

test('refreshAccessToken serializes two module instances via navigator.locks', async () => {
  let accessOk = false
  let meCalls = 0
  let refreshCalls = 0
  const originalFetch = globalThis.fetch
  let lockChain = Promise.resolve()
  const mockLocks = {
    request: async (_name, fn) => {
      const run = lockChain.then(() => fn())
      lockChain = run.then(() => undefined, () => undefined)
      return run
    },
  }
  const nav = globalThis.navigator || {}
  const hadLocks = Object.prototype.hasOwnProperty.call(nav, 'locks')
  const originalLocks = nav.locks
  Object.defineProperty(nav, 'locks', { configurable: true, enumerable: true, writable: true, value: mockLocks })
  if (!globalThis.navigator) globalThis.navigator = nav
  globalThis.fetch = mock.fn(async (url) => {
    const path = typeof url === 'string' ? url : String(url)
    if (path.includes('/auth/me')) {
      meCalls += 1
      return { ok: accessOk, status: accessOk ? 200 : 401 }
    }
    if (path.includes('/auth/refresh')) {
      refreshCalls += 1
      accessOk = true
      return { ok: true, status: 200 }
    }
    throw new Error(`unexpected fetch: ${path}`)
  })
  try {
    const stamp = Date.now()
    const apiA = await import(`../api.js?tabA=${stamp}`)
    const apiB = await import(`../api.js?tabB=${stamp + 1}`)
    const [a, b] = await Promise.all([
      apiA.refreshAccessToken(),
      apiB.refreshAccessToken(),
    ])
    assert.equal(a, true)
    assert.equal(b, true)
    assert.equal(refreshCalls, 1, 'second tab must not POST refresh after the first rotation')
    assert.equal(meCalls, 2, 'second tab must probe /auth/me after taking the lock')
  } finally {
    globalThis.fetch = originalFetch
    if (hadLocks) {
      Object.defineProperty(nav, 'locks', { configurable: true, value: originalLocks })
    } else {
      delete nav.locks
    }
  }
})

test('refreshAccessToken finishes when auth fetches never settle', async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = mock.fn((_url, opts) => new Promise((_resolve, reject) => {
    assert.ok(opts?.signal, 'auth rotation fetch must pass an abort signal')
    const fail = () => {
      const err = new Error('The operation was aborted')
      err.name = 'TimeoutError'
      reject(err)
    }
    const signal = opts.signal
    if (signal.aborted) fail()
    else signal.addEventListener('abort', fail, { once: true })
    setTimeout(fail, 15)
  }))
  try {
    const api = await import(`../api.js?hang=${Date.now()}`)
    const started = Date.now()
    assert.equal(await api.refreshAccessToken(), false)
    assert.ok(Date.now() - started < 2000, 'hung auth fetch must abort instead of holding the lock')
  } finally {
    globalThis.fetch = originalFetch
  }
})
