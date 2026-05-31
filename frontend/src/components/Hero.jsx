import { useState, useEffect, useRef } from 'react'
import './Hero.css'

const STACK_KEY = 'briefr_stack'

export default function Hero({ onBrief }) {
  const [stack, setStack] = useState(() => {
    try { return localStorage.getItem(STACK_KEY) || '' } catch { return '' }
  })
  const inputRef = useRef(null)

  useEffect(() => {
    try { localStorage.setItem(STACK_KEY, stack) } catch {}
  }, [stack])

  function handleBrief() {
    if (stack.trim()) onBrief(stack.trim())
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter') handleBrief()
  }

  return (
    <section className="hero" aria-label="BRIEFR brief">
      <h1 className="hero-heading">
        <em>What broke overnight.</em>
      </h1>
      <p className="hero-sub">
        Live CVE intelligence filtered for your stack. No noise, no filler.
      </p>

      <div className="hero-stack-bar" role="search" aria-label="Filter CVEs by tech stack">
        <label htmlFor="stack-input" className="stack-label">STACK //</label>
        <input
          id="stack-input"
          ref={inputRef}
          type="text"
          className="stack-input"
          value={stack}
          onChange={e => setStack(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="nginx, python, linux kernel, postgres..."
          aria-label="Enter your technology stack to filter CVEs"
          autoComplete="off"
          spellCheck="false"
        />
        <button
          className="stack-brief-btn"
          onClick={handleBrief}
          aria-label="Generate brief for entered stack"
        >
          BRIEF
        </button>
      </div>
    </section>
  )
}
