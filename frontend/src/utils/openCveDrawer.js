import { notifyApiError } from '../components/Toast.jsx'

/**
 * Open a CVE in the detail drawer without reopening after the user closes
 * while a fetch is still in flight.
 */
export function createCveDrawerController({ fetchCVE, setSelectedCVE, setDrawerLoading }) {
  let activeCveId = null
  let requestSeq = 0

  function open(cve) {
    const cveId = cve?.cve_id
    if (!cveId) return
    activeCveId = cveId
    const seq = ++requestSeq
    setSelectedCVE(cve)
    setDrawerLoading(true)
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
          notifyApiError(err)
        }
      })
  }

  function close() {
    activeCveId = null
    requestSeq += 1
    setSelectedCVE(null)
    setDrawerLoading(false)
  }

  function replace(full) {
    if (!full?.cve_id || activeCveId === null) return
    activeCveId = full.cve_id
    setSelectedCVE(full)
    setDrawerLoading(false)
  }

  return { open, close, replace }
}
