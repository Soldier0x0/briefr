import { useId } from 'react'
import * as RadixSwitch from '@radix-ui/react-switch'
import './ui.css'

/**
 * Radix-backed switch primitive (E3-1).
 */
export default function Switch({
  checked,
  defaultChecked,
  onCheckedChange,
  disabled = false,
  id,
  className = '',
  label,
  ...rest
}) {
  const defaultId = useId()
  const switchId = id || defaultId

  const root = (
    <RadixSwitch.Root
      id={switchId}
      className={`ui-switch${className ? ` ${className}` : ''}`}
      checked={checked}
      defaultChecked={defaultChecked}
      onCheckedChange={onCheckedChange}
      disabled={disabled}
      {...rest}
    >
      <RadixSwitch.Thumb className="ui-switch-thumb" />
    </RadixSwitch.Root>
  )

  if (!label) return root

  return (
    <label
      className={`ui-switch-label${disabled ? ' ui-switch-label--disabled' : ''}`}
      htmlFor={switchId}
    >
      {root}
      <span className="ui-switch-label-text">{label}</span>
    </label>
  )
}
