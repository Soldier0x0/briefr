import { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { fetchStatsTimeline } from '../api.js'
import { notifyApiError } from './Toast.jsx'
import { ingestLogUrl } from '../utils/adminLinks.js'
import {
  buildHeatmapGrid,
  heatmapColor,
  HEATMAP_LEGEND_COUNTS,
  weekCountForDays,
} from '../utils/heatmapGrid.js'
import './TimelineHeatmap.css'

const ROW_LABELS = [
  { row: 0, label: 'S' },
  { row: 1, label: 'M' },
  { row: 2, label: 'T' },
  { row: 3, label: 'W' },
  { row: 4, label: 'T' },
  { row: 5, label: 'F' },
  { row: 6, label: 'S' },
]

const DESKTOP_DAYS = 90
const MOBILE_DAYS = 30
const MOBILE_MQ = '(max-width: 640px)'

function formatTooltipDate(isoDate) {
  const d = new Date(`${isoDate}T12:00:00Z`)
  return d.toLocaleDateString(undefined, {
    weekday: 'short',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  })
}

export default function TimelineHeatmap({ filters, onFiltersChange }) {
  const [timeline, setTimeline] = useState([])
  const [loading, setLoading] = useState(true)
  const [collapsed, setCollapsed] = useState(false)
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== 'undefined' && window.matchMedia(MOBILE_MQ).matches
  )
  const [hovered, setHovered] = useState(null)
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 })
  const [error, setError] = useState(null)
  const [errorRequestId, setErrorRequestId] = useState(null)
  const wrapRef = useRef(null)

  const displayDays = isMobile ? MOBILE_DAYS : DESKTOP_DAYS
  const weekCount = weekCountForDays(displayDays)
  const cellSize = isMobile ? 10 : 12

  useEffect(() => {
    const mq = window.matchMedia(MOBILE_MQ)
    const onChange = () => setIsMobile(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  const loadTimeline = useCallback(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setErrorRequestId(null)
    fetchStatsTimeline(DESKTOP_DAYS)
      .then(data => {
        if (!cancelled) setTimeline(Array.isArray(data) ? data : [])
      })
      .catch(err => {
        if (!cancelled) {
          setTimeline([])
          setError(err?.message || 'Failed to load activity timeline.')
          setErrorRequestId(err?.requestId || null)
          notifyApiError(err)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => loadTimeline(), [loadTimeline])

  const slicedTimeline = useMemo(() => {
    if (!timeline.length) return []
    if (timeline.length <= displayDays) return timeline
    return timeline.slice(-displayDays)
  }, [timeline, displayDays])

  const grid = useMemo(
    () => buildHeatmapGrid(slicedTimeline, displayDays, weekCount),
    [slicedTimeline, displayDays, weekCount]
  )

  const hasActivity = useMemo(
    () => slicedTimeline.some(row => (row?.count ?? 0) > 0),
    [slicedTimeline]
  )

  const selectedDate = filters.published_on || ''

  const handleCellEnter = useCallback((cell, event) => {
    if (!cell) return
    const rect = event.currentTarget.getBoundingClientRect()
    const wrapRect = wrapRef.current?.getBoundingClientRect()
    setHovered(cell)
    setTooltipPos({
      x: rect.left + rect.width / 2 - (wrapRect?.left ?? 0),
      y: rect.top - (wrapRect?.top ?? 0) - 8,
    })
  }, [])

  const handleCellClick = useCallback(
    (cell) => {
      if (!cell?.date) return
      const next = selectedDate === cell.date ? '' : cell.date
      onFiltersChange({ published_on: next })
    },
    [onFiltersChange, selectedDate]
  )

  const titleDays = isMobile ? MOBILE_DAYS : DESKTOP_DAYS

  return (
    <section
      className={`timeline-heatmap${collapsed ? ' timeline-heatmap--collapsed' : ''}`}
      aria-label={`${titleDays}-day CVE publication activity`}
    >
      <div className="timeline-heatmap-header">
        <button
          type="button"
          className="timeline-heatmap-toggle"
          onClick={() => setCollapsed(c => !c)}
          aria-expanded={!collapsed}
          aria-controls="timeline-heatmap-body"
          aria-label={collapsed ? 'Expand activity heatmap' : 'Collapse activity heatmap'}
        >
          <span className={`timeline-chevron${collapsed ? ' collapsed' : ''}`} aria-hidden="true">
            ▾
          </span>
        </button>
        <h2 className="timeline-heatmap-title mono">
          // {titleDays}-DAY CVE PUBLICATIONS
        </h2>
      </div>

      {!collapsed && (
        <div id="timeline-heatmap-body" className="timeline-heatmap-body" ref={wrapRef}>
          {loading ? (
            <p className="timeline-heatmap-loading mono" aria-live="polite">
              Loading activity…
            </p>
          ) : error ? (
            <div className="timeline-heatmap-error mono" role="alert">
              <span>
                {error}
                {errorRequestId && (
                  <>
                    {' '}
                    (<a href={ingestLogUrl({ level: 'ERROR', requestId: errorRequestId })}>
                      ref: {errorRequestId}
                    </a>)
                  </>
                )}
              </span>
              <button type="button" className="timeline-heatmap-retry" onClick={loadTimeline}>
                Retry
              </button>
            </div>
          ) : !hasActivity ? (
            <p className="timeline-heatmap-empty-note mono">
              No publication activity in the last {titleDays} days — wait for ingest.
            </p>
          ) : (
            <>
              <div
                className="timeline-heatmap-chart"
                style={{
                  '--heatmap-cell': `${cellSize}px`,
                  '--heatmap-gap': '2px',
                }}
              >
                <div className="timeline-row-labels" aria-hidden="true">
                  {ROW_LABELS.map(({ row, label }) => (
                    <span
                      key={row}
                      className="timeline-row-label mono"
                      style={{ gridRow: row + 1 }}
                    >
                      {label}
                    </span>
                  ))}
                </div>

                <div
                  className="timeline-grid"
                  style={{
                    gridTemplateColumns: `repeat(${weekCount}, ${cellSize}px)`,
                    gridTemplateRows: `repeat(7, ${cellSize}px)`,
                  }}
                  role="grid"
                  aria-label="CVE publication heatmap by day"
                >
                  {grid.map((row, rowIdx) =>
                    row.map((cell, colIdx) => {
                      if (!cell) {
                        return (
                          <span
                            key={`${rowIdx}-${colIdx}`}
                            className="timeline-cell timeline-cell--empty"
                            style={{ gridRow: rowIdx + 1, gridColumn: colIdx + 1 }}
                            aria-hidden="true"
                          />
                        )
                      }
                      const active = selectedDate === cell.date
                      return (
                        <button
                          key={cell.date}
                          type="button"
                          className={`timeline-cell${active ? ' timeline-cell--selected' : ''}`}
                          style={{
                            gridRow: rowIdx + 1,
                            gridColumn: colIdx + 1,
                            background: heatmapColor(cell.count),
                          }}
                          onMouseEnter={e => handleCellEnter(cell, e)}
                          onFocus={e => handleCellEnter(cell, e)}
                          onMouseLeave={() => setHovered(null)}
                          onBlur={() => setHovered(null)}
                          onClick={() => handleCellClick(cell)}
                          aria-label={`${formatTooltipDate(cell.date)}: ${cell.count} CVEs`}
                          aria-pressed={active}
                        />
                      )
                    })
                  )}
                </div>
              </div>

              <div
                className="timeline-heatmap-legend"
                title="Cell colour intensity maps to CVE count published that day (0 = none, darker = more)."
                aria-label="Heatmap legend: lighter cells mean fewer CVEs published that day"
              >
                <span className="timeline-legend-label mono">Less</span>
                <div className="timeline-legend-cells">
                  {HEATMAP_LEGEND_COUNTS.map(n => (
                    <span
                      key={n}
                      className="timeline-legend-swatch"
                      style={{
                        width: cellSize,
                        height: cellSize,
                        background: heatmapColor(n),
                      }}
                    />
                  ))}
                </div>
                <span className="timeline-legend-label mono">More</span>
              </div>

              {hovered && (
                <div
                  className="timeline-tooltip mono"
                  role="tooltip"
                  style={{
                    left: tooltipPos.x,
                    top: tooltipPos.y,
                    transform: 'translate(-50%, -100%)',
                  }}
                >
                  <div className="timeline-tooltip-date">{formatTooltipDate(hovered.date)}</div>
                  <div>{hovered.count.toLocaleString()} CVEs</div>
                  <div>{hovered.critical.toLocaleString()} critical</div>
                  <div>{hovered.kev.toLocaleString()} KEV</div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </section>
  )
}
