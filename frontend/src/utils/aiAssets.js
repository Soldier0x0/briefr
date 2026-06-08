/** AI/ML asset profile helpers (session stack in localStorage). */

import { getSavedStack } from './cveFilters.js'

export const AI_ML_KEYWORDS = [
  'tensorflow',
  'pytorch',
  'torch',
  'langchain',
  'openai',
  'huggingface',
  'transformers',
  'scikit-learn',
  'sklearn',
  'onnx',
  'keras',
  'jax',
  'anthropic',
  'llama',
  'mistral',
  'ollama',
  'stable-diffusion',
  'diffusers',
  'spacy',
  'nltk',
  'gensim',
]

export function getDeclaredAiFrameworks() {
  const stack = getSavedStack().toLowerCase()
  if (!stack) return []
  return AI_ML_KEYWORDS.filter(kw => {
    const re = new RegExp(`\\b${kw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i')
    return re.test(stack)
  })
}

/** Framework tokens for AI/ML alert stats and CVE filtering (stack + session profile). */
export function getAiFrameworksForAlerts(assetProfile = null) {
  const tokens = new Set(getDeclaredAiFrameworks())
  for (const name of assetProfile?.aiSystems || []) {
    const lower = String(name).toLowerCase()
    for (const kw of AI_ML_KEYWORDS) {
      if (lower.includes(kw)) tokens.add(kw)
    }
  }
  return [...tokens]
}

export function hasDeclaredAiAssets(assetProfile = null) {
  return getAiFrameworksForAlerts(assetProfile).length > 0
}

export function aiFrameworksQueryParam(assetProfile = null) {
  const fw = getAiFrameworksForAlerts(assetProfile)
  return fw.length ? fw.join(',') : ''
}

export function cveMatchesDeclaredAi(cve) {
  const frameworks = getDeclaredAiFrameworks()
  if (!frameworks.length || !cve?.has_ai_context) return false
  const text = [
    cve.description || '',
    ...(Array.isArray(cve.affected_products) ? cve.affected_products : []),
  ].join(' ').toLowerCase()
  return frameworks.some(kw => text.includes(kw.toLowerCase()))
}
