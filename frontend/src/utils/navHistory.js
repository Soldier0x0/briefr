/**
 * Shell history SSOT — intentional context changes push; cosmetic URL
 * cleanup replaces. Prevents Browser Back from skipping Forge/FEED and
 * dumping users on login (issue 21 / C13).
 */

/**
 * Intentional navigation that should be Back-able (tab change, Forge pivot,
 * open CVE, Admin page switch).
 *
 * @param {import('react-router-dom').SetURLSearchParams} setSearchParams
 * @param {(prev: URLSearchParams) => URLSearchParams} mutator
 */
export function pushContext(setSearchParams, mutator) {
  setSearchParams(mutator, { replace: false })
}

/**
 * Cosmetic URL cleanup that must NOT create history entries (deep-link
 * param stripping, first-paint tab=/p= hygiene, stale Forge param scrub).
 *
 * @param {import('react-router-dom').SetURLSearchParams} setSearchParams
 * @param {(prev: URLSearchParams) => URLSearchParams} mutator
 */
export function replaceHygiene(setSearchParams, mutator) {
  setSearchParams(mutator, { replace: true })
}
