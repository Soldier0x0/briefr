import { notifyApiError } from '../components/Toast.jsx'

/**
 * Open a CVE in the detail drawer without reopening after the user closes
 * while a fetch is still in flight.
 */
export function createCveDrawerController({ fetchCVE, setSelectedCVE, setDrawerLoading, setDrawerError }) {
  let activeCveId = null
  let requestSeq = 0
  let lastCve = null

  function open(cve) {
    const cveId = cve?.cve_id
    if (!cveId) return
    lastCve = cve
    activeCveId = cveId
    const seq = ++requestSeq
    setSelectedCVE(cve)
    setDrawerLoading(true)
    setDrawerError?.(null)
    fetchCVE(cveId)
      .then(full => {
        if (activeCveId === cveId && seq === requestSeq) {
          setSelectedCVE(full)
          setDrawerLoading(false)
        }
      })
      .catch(err => {
        if (activeCveId === cveId && seq === requestSeq) {
          setDrawerLoading(false)
          setDrawerError?.({
            message: err?.message || 'Failed to load full details.',
            requestId: err?.requestId || null,
          })
          notifyApiError(err)
        }
      })
  }

  function close() {
    activeCveId = null
    requestSeq += 1
    lastCve = null
    setSelectedCVE(null)
    setDrawerLoading(false)
    setDrawerError?.(null)
  }

  function replace(full) {
    if (!full?.cve_id || activeCveId === null) return
    activeCveId = full.cve_id
    setSelectedCVE(full)
    setDrawerLoading(false)
  }

  function retry() {
    if (lastCve) open(lastCve)
  }

  return { open, close, replace, retry }
}
