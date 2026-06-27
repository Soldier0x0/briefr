/** Local file export/import for asset profiles — never touches localStorage or the server. */

const EXPORT_VERSION = 1

export function buildEmptyProfile() {
  return {
    version: EXPORT_VERSION,
    operatingSystems: [],
    applications: [],
    environment: {
      internetFacing: 'Some',
      industry: 'Technology',
      criticality: 'Medium',
    },
    aiSystems: [],
  }
}

export function profileToMatchAssets(profile) {
  if (!profile) return []
  const assets = []

  for (const os of profile.operatingSystems || []) {
    if (!os?.product) continue
    assets.push({
      product: os.product,
      version: os.version || '',
      vendor: os.vendor || '',
    })
  }
  for (const app of profile.applications || []) {
    if (!app?.product) continue
    assets.push({
      product: app.cpeProduct || app.product,
      version: app.version || '',
      vendor: app.vendor || '',
    })
  }
  for (const ai of profile.aiSystems || []) {
    const name = typeof ai === 'string' ? ai : ai?.product
    if (!name) continue
    assets.push({ product: name, version: '', vendor: '' })
  }
  return assets
}

export function downloadProfileJson(profile) {
  const blob = new Blob([JSON.stringify(profile, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `briefr-my-stack-${Date.now()}.json`
  anchor.click()
  URL.revokeObjectURL(url)
}

export async function parseProfileFile(file) {
  const text = await file.text()
  let data
  try {
    data = JSON.parse(text)
  } catch {
    throw new Error('Invalid profile file — not valid JSON')
  }
  if (!data || typeof data !== 'object') {
    throw new Error('Invalid profile file')
  }
  return {
    version: data.version || EXPORT_VERSION,
    operatingSystems: Array.isArray(data.operatingSystems) ? data.operatingSystems : [],
    applications: Array.isArray(data.applications) ? data.applications : [],
    environment: {
      internetFacing: data.environment?.internetFacing || 'Some',
      industry: data.environment?.industry || 'Technology',
      criticality: data.environment?.criticality || 'Medium',
    },
    aiSystems: Array.isArray(data.aiSystems) ? data.aiSystems : [],
  }
}
