import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import useModalLayer from '../hooks/useModalLayer.js'
import './TutorialOverlay.css'

const STEPS = [
  {
    tab: null,
    target: null,
    title: 'Welcome to BRIEFR',
    body: 'BRIEFR aggregates CVE, KEV, and threat intel into one dashboard. This quick tour covers the basics — skip anytime.',
  },
  {
    tab: 'brief',
    target: '[aria-label="Switch to morning brief"]',
    title: 'BRIEF',
    body: 'Your daily snapshot: trending CVEs, stats, and what changed since your last visit.',
  },
  {
    tab: 'feed',
    target: '[aria-label="Switch to full CVE feed"]',
    title: 'FEED',
    body: 'Search and filter the full CVE list here. Press / to jump to search, F to cycle quick filters.',
  },
  {
    tab: 'feed',
    target: null,
    title: 'CVE details',
    body: 'Click any CVE to open full details — references, exploitation status, and detection guidance.',
  },
  {
    tab: 'ioc',
    target: '[aria-label="Switch to IOC lookup"]',
    title: 'IOC LOOKUP',
    body: 'Look up IPs, hashes, and domains against threat intel sources.',
  },
  {
    tab: 'atlas',
    target: '[aria-label="Switch to incidents and news"]',
    title: 'ADVISORIES & INTEL + FORGE',
    body: 'Advisories & Intel holds headline news, structured advisories, and ATLAS case studies. Forge is for detection engineering. Re-open this tour anytime from the ⋯ menu — "Show tutorial again".',
  },
]

export default function TutorialOverlay({ onClose, activeTab, onTabChange }) {
  const [stepIndex, setStepIndex] = useState(0)
  const [rect, setRect] = useState(null)
  const boxRef = useRef(null)
  const step = STEPS[stepIndex]
  const isFirst = stepIndex === 0
  const isLast = stepIndex === STEPS.length - 1

  useModalLayer(true, boxRef, { trackDepth: true })

  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  // eslint-disable-next-line react-hooks/exhaustive-deps -- only re-run on step change, not every activeTab change
  useEffect(() => {
    if (step.tab && step.tab !== activeTab) onTabChange(step.tab)
  }, [stepIndex])

  useLayoutEffect(() => {
    function update() {
      if (!step.target) { setRect(null); return }
      const el = document.querySelector(step.target)
      setRect(el ? el.getBoundingClientRect() : null)
    }
    update()
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [stepIndex])

  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === 'Escape') { e.preventDefault(); onClose() }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  function handleNext() {
    if (isLast) { onClose(); return }
    setStepIndex(i => i + 1)
  }

  function handleBack() {
    setStepIndex(i => Math.max(0, i - 1))
  }

  const calloutStyle = rect
    ? {
        top: rect.bottom + 14,
        left: Math.max(12, Math.min(rect.left, window.innerWidth - 332)),
      }
    : undefined

  return (
    <div className="tutorial-overlay" role="dialog" aria-modal="true" aria-labelledby="tutorial-title">
      <div className="tutorial-scrim" />
      {rect && (
        <div
          className="tutorial-spotlight"
          style={{
            top: rect.top - 6,
            left: rect.left - 6,
            width: rect.width + 12,
            height: rect.height + 12,
          }}
        />
      )}
      <div
        className={`tutorial-callout${rect ? '' : ' tutorial-callout--centered'}`}
        style={calloutStyle}
        ref={boxRef}
        tabIndex={-1}
      >
        <button className="tutorial-close" onClick={onClose} aria-label="Close tutorial (Escape)">
          &#x2715;
        </button>
        <div className="tutorial-step-count mono">{stepIndex + 1} / {STEPS.length}</div>
        <h2 className="tutorial-title" id="tutorial-title">{step.title}</h2>
        <p className="tutorial-body">{step.body}</p>
        <div className="tutorial-actions">
          <button type="button" className="tutorial-skip" onClick={onClose}>Skip</button>
          <div className="tutorial-nav-btns">
            {!isFirst && (
              <button type="button" className="tutorial-back" onClick={handleBack}>Back</button>
            )}
            <button type="button" className="tutorial-next" onClick={handleNext}>
              {isLast ? 'Done' : 'Next'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
