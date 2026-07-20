/** Local file export/import for asset profiles — never touches localStorage or the server. */

const EXPORT_VERSION = 1

const SCORING_CRITICALITY = new Set(['MISSION_CRITICAL', 'IMPORTANT', 'SUPPORTING'])

function normalizeScoringCriticality(value) {
  if (value == null || value === '') return null
  const v = String(value).trim().toUpperCase()
  return SCORING_CRITICALITY.has(v) ? v : null
}

function normalizeOptionalBool(value) {
  if (value === undefined || value === null) return null
  return !!value
}

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
    // W5 OP/SSVC exposure flags (absent / null = today's scoring behaviour)
    internet_facing: null,
    criticality: null,
    privileged_service: null,
    ot_safety: null,
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
    internet_facing: Object.prototype.hasOwnProperty.call(data, 'internet_facing')
      ? normalizeOptionalBool(data.internet_facing)
      : null,
    criticality: normalizeScoringCriticality(data.criticality),
    privileged_service: Object.prototype.hasOwnProperty.call(data, 'privileged_service')
      ? normalizeOptionalBool(data.privileged_service)
      : null,
    ot_safety: Object.prototype.hasOwnProperty.call(data, 'ot_safety')
      ? normalizeOptionalBool(data.ot_safety)
      : null,
    aiSystems: Array.isArray(data.aiSystems) ? data.aiSystems : [],
  }
}
