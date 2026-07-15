import { forwardRef } from 'react'
import * as RadixDropdown from '@radix-ui/react-dropdown-menu'
import './ui.css'

/**
 * Radix-backed dropdown menu primitive (E3-5).
 */
export const DropdownMenu = RadixDropdown.Root
export const DropdownMenuTrigger = RadixDropdown.Trigger
export const DropdownMenuPortal = RadixDropdown.Portal
export const DropdownMenuGroup = RadixDropdown.Group
export const DropdownMenuSub = RadixDropdown.Sub
export const DropdownMenuRadioGroup = RadixDropdown.RadioGroup
export const DropdownMenuCheckboxItem = RadixDropdown.CheckboxItem
export const DropdownMenuRadioItem = RadixDropdown.RadioItem
export const DropdownMenuSubTrigger = RadixDropdown.SubTrigger
export const DropdownMenuSubContent = RadixDropdown.SubContent
export const DropdownMenuArrow = RadixDropdown.Arrow

export const DropdownMenuContent = forwardRef(function DropdownMenuContent(
  { className = '', sideOffset = 4, ...props },
  ref,
) {
  return (
    <RadixDropdown.Portal>
      <RadixDropdown.Content
        ref={ref}
        sideOffset={sideOffset}
        className={['ui-dropdown-content', className].filter(Boolean).join(' ')}
        {...props}
      />
    </RadixDropdown.Portal>
  )
})

export const DropdownMenuItem = forwardRef(function DropdownMenuItem(
  { className = '', ...props },
  ref,
) {
  return (
    <RadixDropdown.Item
      ref={ref}
      className={['ui-dropdown-item', className].filter(Boolean).join(' ')}
      {...props}
    />
  )
})

export const DropdownMenuLabel = forwardRef(function DropdownMenuLabel(
  { className = '', ...props },
  ref,
) {
  return (
    <RadixDropdown.Label
      ref={ref}
      className={['ui-dropdown-label', className].filter(Boolean).join(' ')}
      {...props}
    />
  )
})

export const DropdownMenuSeparator = forwardRef(function DropdownMenuSeparator(
  { className = '', ...props },
  ref,
) {
  return (
    <RadixDropdown.Separator
      ref={ref}
      className={['ui-dropdown-separator', className].filter(Boolean).join(' ')}
      {...props}
    />
  )
})

export default DropdownMenu
