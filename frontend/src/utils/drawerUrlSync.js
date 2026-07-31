/** Whether URL sync should close the drawer when ?cve= disappears. */
export function shouldCloseDrawerOnCveUrlRemoval(hadCveInUrl, cveParam) {
  return Boolean(hadCveInUrl) && !cveParam
}
