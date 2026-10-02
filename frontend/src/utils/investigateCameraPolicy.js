export function shouldRefitAfterStructuralChange({ structuralVersion, lastFitVersion }) {
  return structuralVersion !== lastFitVersion
}

export function nextStructuralVersion(current, reason) {
  if (!reason) return current
  return current + 1
}

export function cameraActionForStructuralChange(reason) {
  switch (reason) {
    case 'resolve':
      return 'fit_all'
    case 'expand':
    case 'load_more':
      return 'fly_neighborhood'
    case 'filter':
    case 'layer':
      return 'fit_visible'
    default:
      return 'none'
  }
}

export function structuralReasonForExpand(params) {
  return params?.cursor ? 'load_more' : 'expand'
}
