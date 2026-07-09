import { useId, useState, useRef, useEffect } from 'react'

/**
 * @param {object} props
 * @param {string} props.text - Tooltip content.
 * @param {React.ReactNode} props.children - Trigger element (must accept ref/focus).
 */
export default function Tooltip({ text, children }) {
  const id = useId()
  const wrapRef = useRef(null)
  const [flip, setFlip] = useState(false)
  const [touchOpen, setTouchOpen] = useState(false)

  useEffect(() => {
    const el = wrapRef.current
    if (!el || !text) return undefined
    const bubble = el.querySelector('.ui-tooltip-bubble')
    if (!bubble) return undefined

    function checkFlip() {
      const rect = bubble.getBoundingClientRect()
      setFlip(rect.top < 8)
    }

    checkFlip()
    window.addEventListener('resize', checkFlip)
    return () => window.removeEventListener('resize', checkFlip)
  }, [text])

  if (!text) return children

  function onKeyDown(e) {
    if (e.key === 'Escape') setTouchOpen(false)
  }

  function onTouchStart() {
    setTouchOpen(o => !o)
  }

  return (
    <span
      ref={wrapRef}
      className={`ui-tooltip-wrap${touchOpen ? ' ui-tooltip-wrap--open' : ''}`}
      onKeyDown={onKeyDown}
      onTouchStart={onTouchStart}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) setTouchOpen(false)
      }}
    >
      <span
        className="ui-tooltip-trigger"
        tabIndex={0}
        aria-describedby={id}
      >
        {children}
      </span>
      <span
        role="tooltip"
        id={id}
        className={`ui-tooltip-bubble${flip ? ' ui-tooltip-bubble--flip' : ''}`}
      >
        {text}
      </span>
    </span>
  )
}
