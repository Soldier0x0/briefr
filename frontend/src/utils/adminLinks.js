/** Deep links into admin log / health pages for troubleshooting. */

function buildAdminUrl(page, params = {}) {
  const sp = new URLSearchParams({ p: page })
  for (const [key, value] of Object.entries(params)) {
    if (value != null && value !== '') sp.set(key, value)
  }
  return `/admin?${sp.toString()}`
}

export function ingestLogUrl({ level, category, logger, requestId } = {}) {
  return buildAdminUrl('ingestlog', {
    level,
    category,
    logger,
    request_id: requestId,
  })
}

export function auditLogUrl({ actionPrefix, q } = {}) {
  return buildAdminUrl('auditlog', {
    action_prefix: actionPrefix,
    q,
  })
}

export function feedHealthUrl({ source } = {}) {
  return buildAdminUrl('feedhealth', { source })
}

export function schedulerUrl({ highlight } = {}) {
  return buildAdminUrl('scheduler', { highlight })
}

/** Primary troubleshooting links for an admin operation kind. */
export function linksForOperation(kind, meta = {}) {
  const links = []
  const jobId = meta.jobId || meta.job_id
  const sourceId = meta.sourceId || meta.source_id
  const requestId = meta.requestId || meta.request_id

  switch (kind) {
    case 'ingest':
      links.push(
        { label: 'View application log', href: ingestLogUrl({ category: 'Scheduler', level: meta.error ? 'ERROR' : '' }) },
        { label: 'Feed health', href: feedHealthUrl() },
      )
      break
    case 'job':
      links.push(
        { label: 'View application log', href: ingestLogUrl({ category: 'Scheduler', logger: 'scheduler', level: meta.error ? 'ERROR' : '' }) },
        { label: 'View audit log', href: auditLogUrl({ actionPrefix: 'scheduler.', q: jobId }) },
      )
      if (!links.some(l => l.href.includes('scheduler'))) {
        links.push({ label: 'Scheduler', href: schedulerUrl({ highlight: jobId }) })
      }
      break
    case 'feed':
      links.push(
        { label: 'Feed health', href: feedHealthUrl({ source: sourceId }) },
        { label: 'View application log', href: ingestLogUrl({ level: meta.error ? 'ERROR' : '', category: 'Scheduler' }) },
      )
      break
    case 'circuit':
      links.push(
        { label: 'Feed health', href: feedHealthUrl({ source: sourceId }) },
        { label: 'View application log', href: ingestLogUrl({ level: 'ERROR' }) },
      )
      break
    case 'incident':
      links.push(
        { label: 'Feed health', href: feedHealthUrl() },
        { label: 'View application log', href: ingestLogUrl({ category: 'Scheduler', level: meta.error ? 'ERROR' : '' }) },
      )
      break
    default:
      links.push({ label: 'View application log', href: ingestLogUrl({ level: meta.error ? 'ERROR' : '', requestId }) })
      break
  }

  if (requestId && !links.some(l => l.href.includes('request_id'))) {
    links.unshift({
      label: 'Filter by request ID',
      href: ingestLogUrl({ requestId }),
    })
  }

  return links.slice(0, 3)
}
