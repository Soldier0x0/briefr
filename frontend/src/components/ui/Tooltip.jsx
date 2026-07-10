import {
  cloneElement,
  isValidElement,
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
} from 'react'
import { createPortal } from 'react-dom'

const GAP = 8
const VIEWPORT_PAD = 8

let dismissActive = null
let activeTooltipId = null

function clamp(n, min, max) {
  return Math.min(max, Math.max(min, n))
}

/**
 * Portaled tooltip — single coordinator closes the previous bubble when a new one opens.
 *
 * @param {object} props
 * @param {string} props.text
 * @param {React.ReactNode} props.children
 * @param {boolean} [props.asChild] - merge aria props into the child element
 * @param {'hover'|'hover-focus'} [props.trigger] - hover-only avoids sticky filter tooltips after click
 * @param {string} [props.className] - wrapper class
 * @param {string} [props.bubbleClassName] - bubble class extension
 * @param {number} [props.maxWidth=280]
 */
export default function Tooltip({
  text,
  children,
  asChild = false,
  trigger = 'hover-focus',
  className = '',
  bubbleClassName = '',
  maxWidth = 280,
}) {
  const id = useId()
  const wrapRef = useRef(null)
  const [open, setOpen] = useState(false)
  const [coords, setCoords] = useState({ top: 0, left: 0, placement: 'top' })

  const updatePosition = useCallback(() => {
    const el = wrapRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const placeAbove = rect.top > 100
    const placement = placeAbove ? 'top' : 'bottom'
    const top = placeAbove ? rect.top - GAP : rect.bottom + GAP
    const left = clamp(rect.left + rect.width / 2, VIEWPORT_PAD + maxWidth / 2, window.innerWidth - VIEWPORT_PAD - maxWidth / 2)
    setCoords({ top, left, placement })
  }, [maxWidth])

  const show = useCallback(() => {
    if (!text) return
    if (dismissActive && activeTooltipId !== id) {
      dismissActive()
    }
    dismissActive = () => setOpen(false)
    activeTooltipId = id
    setOpen(true)
    updatePosition()
  }, [text, updatePosition, id])

  const hide = useCallback(() => {
    setOpen(false)
    if (activeTooltipId === id) {
      dismissActive = null
      activeTooltipId = null
    }
  }, [id])

  useEffect(() => {
    if (!open) return undefined
    updatePosition()
    const onScroll = () => updatePosition()
    window.addEventListener('scroll', onScroll, true)
    window.addEventListener('resize', onScroll)
    return () => {
      window.removeEventListener('scroll', onScroll, true)
      window.removeEventListener('resize', onScroll)
    }
  }, [open, updatePosition])

  useEffect(() => () => {
    if (activeTooltipId === id) {
      dismissActive = null
      activeTooltipId = null
    }
  }, [id])

  if (!text) return children

  const hoverHandlers = {
    onMouseEnter: show,
    onMouseLeave: hide,
  }

  const focusHandlers = trigger === 'hover-focus'
    ? {
        onFocus: show,
        onBlur: (e) => {
          if (!e.currentTarget.contains(e.relatedTarget)) hide()
        },
      }
    : {}

  const child = asChild && isValidElement(children)
    ? cloneElement(children, {
        'aria-describedby': [children.props?.['aria-describedby'], id].filter(Boolean).join(' ') || id,
      })
    : children

  const bubble = open && typeof document !== 'undefined'
    ? createPortal(
        <span
          role="tooltip"
          id={id}
          className={`ui-tooltip-bubble ui-tooltip-bubble--portal ui-tooltip-bubble--${coords.placement} ${bubbleClassName}`.trim()}
          style={{
            position: 'fixed',
            top: coords.top,
            left: coords.left,
            transform: coords.placement === 'top'
              ? 'translate(-50%, -100%)'
              : 'translate(-50%, 0)',
            maxWidth,
            zIndex: 10000,
          }}
        >
          {text}
        </span>,
        document.body,
      )
    : null

  return (
    <>
      <span
        ref={wrapRef}
        className={`ui-tooltip-wrap ${className}`.trim()}
        {...hoverHandlers}
        {...focusHandlers}
      >
        {asChild ? child : (
          <span className="ui-tooltip-trigger" tabIndex={trigger === 'hover-focus' ? 0 : undefined} aria-describedby={id}>
            {children}
          </span>
        )}
      </span>
      {bubble}
    </>
  )
}
