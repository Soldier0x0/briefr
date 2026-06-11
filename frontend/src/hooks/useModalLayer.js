import { useEffect } from 'react'

// Overlay depth registry — overlays that handle their own Escape (PDF modal,
// shortcuts panel) register here so the global App handler stands down while
// they are open. One Escape press must never close two layers.
let depth = 0

export function overlayDepth() {
  return depth
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), ' +
  'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

function focusableIn(container) {
  return Array.from(container.querySelectorAll(FOCUSABLE)).filter(
    el => el.offsetWidth > 0 || el.offsetHeight > 0 || el === document.activeElement,
  )
}

/**
 * Modal layer behavior: focus trap (Tab cycles inside the container) and
 * focus restore to the triggering element on close. Optionally registers in
 * the overlay-depth registry for overlays that own their Escape handling.
 */
export default function useModalLayer(active, containerRef, options = {}) {
  const { trackDepth = false, trapFocus = true } = options

  useEffect(() => {
    if (!active) return
    if (trackDepth) depth += 1
    const previouslyFocused = document.activeElement

    const container = trapFocus ? containerRef.current : null
    if (container) {
      const first = focusableIn(container)[0]
      ;(first || container).focus?.()
    }

    function onKeyDown(e) {
      if (!trapFocus || e.key !== 'Tab') return
      const el = containerRef.current
      if (!el) return
      const nodes = focusableIn(el)
      if (!nodes.length) return
      const first = nodes[0]
      const last = nodes[nodes.length - 1]
      const current = document.activeElement
      const inside = el.contains(current)

      if (e.shiftKey) {
        if (!inside || current === first) {
          e.preventDefault()
          last.focus()
        }
      } else if (!inside || current === last) {
        e.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown, true)
    return () => {
      if (trackDepth) depth = Math.max(0, depth - 1)
      document.removeEventListener('keydown', onKeyDown, true)
      if (previouslyFocused && document.contains(previouslyFocused)) {
        previouslyFocused.focus?.()
      }
    }
  }, [active, containerRef, trackDepth, trapFocus])
}
