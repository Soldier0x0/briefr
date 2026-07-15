import {
  cloneElement,
  isValidElement,
  useState,
} from 'react'
import * as TooltipPrimitive from '@radix-ui/react-tooltip'

const FOCUSABLE_TAGS = new Set(['a', 'button', 'input', 'select', 'textarea'])

function childCanReceiveFocus(child) {
  if (!isValidElement(child)) return false
  if (typeof child.props?.tabIndex === 'number' && child.props.tabIndex >= 0) return true
  if (child.props?.href != null) return true
  const tag = typeof child.type === 'string' ? child.type.toLowerCase() : ''
  return FOCUSABLE_TAGS.has(tag)
}

export function TooltipProvider({
  children,
  delayDuration = 200,
  skipDelayDuration = 0,
}) {
  return (
    <TooltipPrimitive.Provider delayDuration={delayDuration} skipDelayDuration={skipDelayDuration}>
      {children}
    </TooltipPrimitive.Provider>
  )
}

export const TooltipRoot = TooltipPrimitive.Root
export const TooltipTrigger = TooltipPrimitive.Trigger

export function TooltipContent({
  children,
  className = '',
  sideOffset = 6,
  maxWidth = 280,
  ...props
}) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        sideOffset={sideOffset}
        className={`ui-tooltip-content ${className}`.trim()}
        style={{ maxWidth }}
        {...props}
      >
        {children}
      </TooltipPrimitive.Content>
    </TooltipPrimitive.Portal>
  )
}

function HoverOnlyTooltip({
  text,
  children,
  asChild = false,
  className = '',
  bubbleClassName = '',
  maxWidth = 280,
}) {
  const [open, setOpen] = useState(false)

  const triggerChild = asChild && isValidElement(children)
    ? children
    : (
        <span className="ui-tooltip-trigger" tabIndex={-1}>
          {children}
        </span>
      )

  return (
    <span className={`ui-tooltip-wrap ${className}`.trim()}>
      <TooltipPrimitive.Root open={open}>
        <TooltipPrimitive.Trigger
          asChild
          onPointerEnter={() => setOpen(true)}
          onPointerLeave={() => setOpen(false)}
        >
          {triggerChild}
        </TooltipPrimitive.Trigger>
        <TooltipContent className={bubbleClassName} maxWidth={maxWidth}>
          {text}
        </TooltipContent>
      </TooltipPrimitive.Root>
    </span>
  )
}

/**
 * Radix-based tooltip primitive (shadcn pattern): TooltipTrigger + TooltipContent.
 * Legacy `text` prop API preserved for existing call sites.
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
  if (!text) return children

  if (trigger === 'hover') {
    return (
      <HoverOnlyTooltip
        text={text}
        asChild={asChild}
        className={className}
        bubbleClassName={bubbleClassName}
        maxWidth={maxWidth}
      >
        {children}
      </HoverOnlyTooltip>
    )
  }

  const triggerChild = asChild && isValidElement(children)
    ? cloneElement(children, {
        ...(trigger === 'hover-focus' && !childCanReceiveFocus(children) ? { tabIndex: 0 } : {}),
      })
    : (
        <span className={`ui-tooltip-trigger ${className}`.trim()} tabIndex={0}>
          {children}
        </span>
      )

  return (
    <span className={`ui-tooltip-wrap ${className}`.trim()}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild>
          {triggerChild}
        </TooltipPrimitive.Trigger>
        <TooltipContent className={bubbleClassName} maxWidth={maxWidth}>
          {text}
        </TooltipContent>
      </TooltipPrimitive.Root>
    </span>
  )
}
