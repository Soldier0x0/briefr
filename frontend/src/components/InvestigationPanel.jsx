import { useState } from 'react'
import { useInvestigation, INV_TYPES } from '../context/InvestigationContext.jsx'
import PdfExportModal from './PdfExportModal.jsx'
import './InvestigationPanel.css'

function typeBadge(type) {
  switch (type) {
    case INV_TYPES.CVE: return 'CVE'
    case INV_TYPES.IOC: return 'IOC'
    case INV_TYPES.ACTOR: return 'ACTOR'
    case INV_TYPES.TECHNIQUE: return 'AI'
    default: return '—'
  }
}

function formatElapsed(ms, fromTs) {
  const delta = Math.max(0, ms - fromTs)
  const sec = Math.floor(delta / 1000)
  if (sec < 60) return `${sec}s`
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min}m`
  return `${Math.floor(min / 60)}h ${min % 60}m`
}

function ThreadList({ items, startTime, pivotLabel }) {
  return (
    <ol className="inv-thread-list">
      {items.map((item, idx) => (
        <li key={item.key} className="inv-thread-item">
          {idx > 0 && item.pivotFrom && (
            <div className="inv-pivot-arrow mono" aria-hidden="true">
              <span className="inv-pivot-from">{pivotLabel(item.pivotFrom)}</span>
              <span className="inv-pivot-chevron">↓</span>
            </div>
          )}
          <div className="inv-thread-card">
            <div className="inv-thread-top">
              <span className={`inv-type-badge inv-type-${item.type}`}>{typeBadge(item.type)}</span>
              <span className="inv-thread-time mono">
                +{formatElapsed(item.timestamp, startTime)}
              </span>
            </div>
            <span className="inv-thread-id mono">{item.title || item.id}</span>
            {item.description && (
              <p className="inv-thread-desc">{item.description}</p>
            )}
          </div>
        </li>
      ))}
    </ol>
  )
}

function PanelChrome({ expanded, onToggle, onPdf, onClear, count }) {
  if (!expanded) {
    return (
      <div className="inv-panel-collapsed">
        <button
          type="button"
          className="inv-strip-expand mono"
          onClick={onToggle}
          aria-label={`Expand investigation thread (${count} items)`}
          title="Expand investigation"
        >
          <span className="inv-strip-count">{count}</span>
        </button>
        <button
          type="button"
          className="inv-strip-pdf mono"
          onClick={onPdf}
          title="Download investigation PDF"
        >
          PDF
        </button>
      </div>
    )
  }

  return (
    <div className="inv-panel-expanded">
      <div className="inv-panel-head">
        <button
          type="button"
          className="inv-panel-collapse mono"
          onClick={onToggle}
          aria-label="Collapse investigation panel"
        >
          ‹
        </button>
        <span className="inv-panel-title mono">// INVESTIGATION</span>
        <span className="inv-panel-count mono">{count}</span>
      </div>
      <div className="inv-panel-actions">
        <button type="button" className="inv-action-btn inv-action-pdf mono" onClick={onPdf}>
          ↓ PDF
        </button>
        <button type="button" className="inv-action-btn mono" onClick={onClear}>
          Clear
        </button>
      </div>
    </div>
  )
}

export default function InvestigationPanel() {
  const {
    items,
    startTime,
    showPanel,
    threadSummary,
    panelExpanded,
    setPanelExpanded,
    mobileSheetOpen,
    setMobileSheetOpen,
    clearInvestigation,
    pivotLabel,
  } = useInvestigation()

  const [pdfModalOpen, setPdfModalOpen] = useState(false)
  const [pdfBusy, setPdfBusy] = useState(false)
  const [pdfError, setPdfError] = useState(null)

  if (!showPanel || !startTime) return null

  async function handlePdfConfirm({ analystName }) {
    setPdfBusy(true)
    setPdfError(null)
    try {
      const { downloadInvestigationPdf } = await import('../utils/investigationPdf.js')
      await downloadInvestigationPdf(items, startTime, { analystName })
      setPdfModalOpen(false)
    } catch (err) {
      setPdfError(err?.message || 'PDF generation failed.')
    } finally {
      setPdfBusy(false)
    }
  }

  const count = items.length

  return (
    <>
      <aside
        className={`inv-panel-desktop${panelExpanded ? ' inv-panel-desktop--open' : ''}`}
        aria-label="Investigation thread"
      >
        <PanelChrome
          expanded={panelExpanded}
          onToggle={() => setPanelExpanded(e => !e)}
          onPdf={() => { setPdfError(null); setPdfModalOpen(true) }}
          onClear={clearInvestigation}
          count={count}
        />
        {panelExpanded && (
          <>
            <p className="inv-thread-summary mono">{threadSummary}</p>
            {count === 1 && (
              <p className="inv-thread-hint">
                Pivot to IOC or ATLAS, or export a PDF when you are ready.
              </p>
            )}
            <ThreadList items={items} startTime={startTime} pivotLabel={pivotLabel} />
          </>
        )}
      </aside>

      <div className="inv-mobile-wrap">
        <button
          type="button"
          className="inv-mobile-fab mono"
          onClick={() => setMobileSheetOpen(true)}
          aria-label={`Open investigation thread, ${count} items`}
        >
          {count} items
        </button>
      </div>

      {mobileSheetOpen && (
        <div
          className="inv-sheet-overlay"
          role="presentation"
          onClick={() => setMobileSheetOpen(false)}
        >
          <div
            className="inv-sheet"
            role="dialog"
            aria-label="Investigation thread"
            onClick={e => e.stopPropagation()}
          >
            <div className="inv-sheet-head">
              <span className="mono">// INVESTIGATION ({count})</span>
              <button
                type="button"
                className="inv-sheet-close"
                onClick={() => setMobileSheetOpen(false)}
                aria-label="Close"
              >
                ×
              </button>
            </div>
            <div className="inv-panel-actions inv-panel-actions--sheet">
              <button type="button" className="inv-action-btn inv-action-pdf mono" onClick={() => { setPdfError(null); setPdfModalOpen(true) }}>
                ↓ PDF
              </button>
              <button type="button" className="inv-action-btn mono" onClick={clearInvestigation}>
                Clear
              </button>
            </div>
            <p className="inv-thread-summary mono">{threadSummary}</p>
            {count === 1 && (
              <p className="inv-thread-hint">
                Pivot to IOC or ATLAS, or export a PDF when you are ready.
              </p>
            )}
            <ThreadList items={items} startTime={startTime} pivotLabel={pivotLabel} />
          </div>
        </div>
      )}

      <PdfExportModal
        open={pdfModalOpen}
        title="Investigation PDF report"
        busy={pdfBusy}
        error={pdfError}
        onConfirm={handlePdfConfirm}
        onCancel={() => {
          if (!pdfBusy) {
            setPdfModalOpen(false)
            setPdfError(null)
          }
        }}
      />
    </>
  )
}
