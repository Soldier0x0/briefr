/**
 * Open a CVE in the detail drawer without reopening after the user closes
 * while a fetch is still in flight.
 */
function hasDrawerPreview(cve) {
  if (!cve?.cve_id) return false
  return Boolean(
    cve.description ||
    cve.summary ||
    cve.cvss_score != null ||
    cve.severity ||
    cve.is_kev != null,
  )
}

export function createCveDrawerController({ fetchCVE, setSelectedCVE, setDrawerLoading }) {
  let activeCveId = null
  let requestSeq = 0

  function open(cve) {
    const cveId = cve?.cve_id
    if (!cveId) return
    activeCveId = cveId
    const seq = ++requestSeq
    setSelectedCVE(cve)
    // List/brief rows already carry enough data to render the drawer; only
    // block the UI when opening a bare CVE id (deep link / IOC pivot).
    setDrawerLoading(!hasDrawerPreview(cve))
    fetchCVE(cveId)
      .then(full => {
        if (activeCveId === cveId && seq === requestSeq) {
          setSelectedCVE(full)
          setDrawerLoading(false)
        }
      })
      .catch(() => {
        if (activeCveId === cveId && seq === requestSeq) {
          setDrawerLoading(false)
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
