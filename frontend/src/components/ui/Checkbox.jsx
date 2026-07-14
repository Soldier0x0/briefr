import * as RadixCheckbox from '@radix-ui/react-checkbox'
import { Check } from 'lucide-react'
import './ui.css'

/**
 * Radix-backed checkbox primitive (ADR-003 / E0-2 reference implementation).
 * @param {object} props
 * @param {boolean} [props.checked]
 * @param {boolean} [props.defaultChecked]
 * @param {(checked: boolean) => void} [props.onCheckedChange]
 * @param {boolean} [props.disabled]
 * @param {string} [props.id]
 * @param {string} [props.className]
 * @param {string} [props.label] Optional visible label (renders as sibling)
 */
export default function Checkbox({
  checked,
  defaultChecked,
  onCheckedChange,
  disabled = false,
  id,
  className = '',
  label,
  ...rest
}) {
  const root = (
    <RadixCheckbox.Root
      id={id}
      className="ui-checkbox"
      checked={checked}
      defaultChecked={defaultChecked}
      onCheckedChange={onCheckedChange}
      disabled={disabled}
    >
      <RadixCheckbox.Indicator className="ui-checkbox-indicator">
        <Check size={14} strokeWidth={2.5} aria-hidden="true" />
      </RadixCheckbox.Indicator>
    </RadixCheckbox.Root>
  )

  if (!label) {
    return (
      <RadixCheckbox.Root
        id={id}
        className={`ui-checkbox${className ? ` ${className}` : ''}`}
        checked={checked}
        defaultChecked={defaultChecked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        {...rest}
      >
        <RadixCheckbox.Indicator className="ui-checkbox-indicator">
          <Check size={14} strokeWidth={2.5} aria-hidden="true" />
        </RadixCheckbox.Indicator>
      </RadixCheckbox.Root>
    )
  }

  return (
    <label
      className={`ui-checkbox-label${className ? ` ${className}` : ''}`}
      htmlFor={id}
      {...rest}
    >
      {root}
      <span className="ui-checkbox-label-text">{label}</span>
    </label>
  )
}
