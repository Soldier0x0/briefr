import { forwardRef } from 'react'
import * as RadixPopover from '@radix-ui/react-popover'
import './ui.css'

export const Popover = RadixPopover.Root
export const PopoverTrigger = RadixPopover.Trigger
export const PopoverAnchor = RadixPopover.Anchor

export const PopoverContent = forwardRef(function PopoverContent(
  { className = '', sideOffset = 6, align = 'end', ...props },
  ref,
) {
  return (
    <RadixPopover.Portal>
      <RadixPopover.Content
        ref={ref}
        sideOffset={sideOffset}
        align={align}
        className={['ui-popover-content', className].filter(Boolean).join(' ')}
        {...props}
      />
    </RadixPopover.Portal>
  )
})

export default Popover
