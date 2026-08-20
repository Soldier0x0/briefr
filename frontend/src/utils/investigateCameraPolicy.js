export function shouldRefitAfterStructuralChange({ structuralVersion, lastFitVersion }) {
  return structuralVersion !== lastFitVersion
}

export function nextStructuralVersion(current, reason) {
  if (!reason) return current
  return current + 1
}
