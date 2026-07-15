import { forwardRef } from 'react'
import * as RadixSelect from '@radix-ui/react-select'
import { Check, ChevronDown } from 'lucide-react'
import './ui.css'

const EMPTY_VALUE = '__radix_empty__'

function toRadixValue(value) {
  if (value === '' || value === undefined || value === null) return EMPTY_VALUE
  return String(value)
}

function fromRadixValue(value) {
  if (value === EMPTY_VALUE) return ''
  return value
}

/**
 * Radix-backed select primitive (E3-5).
 * @param {object} props
 * @param {string} [props.value]
 * @param {string} [props.defaultValue]
 * @param {(value: string) => void} [props.onValueChange]
 * @param {(value: string) => void} [props.onChange] Alias for onValueChange
 * @param {Array<{value: string, label: React.ReactNode, disabled?: boolean}>} [props.options]
 * @param {string} [props.placeholder]
 * @param {boolean} [props.disabled]
 * @param {string} [props.id]
 * @param {string} [props.name]
 * @param {string} [props.className] Applied to the trigger
 * @param {string} [props['aria-label']]
 */
const Select = forwardRef(function Select(
  {
    value,
    defaultValue,
    onValueChange,
    onChange,
    options = [],
    placeholder,
    disabled = false,
    id,
    name,
    className = '',
    style,
    'aria-label': ariaLabel,
    children,
    ...rest
  },
  ref,
) {
  const handleChange = (next) => {
    const mapped = fromRadixValue(next)
    onValueChange?.(mapped)
    onChange?.(mapped)
  }

  const triggerClass = ['ui-select-trigger', 'admin-select', className].filter(Boolean).join(' ')

  const rootProps = {
    onValueChange: handleChange,
    disabled,
    name,
  }

  if (value !== undefined) {
    rootProps.value = toRadixValue(value)
  }
  if (defaultValue !== undefined) {
    rootProps.defaultValue = toRadixValue(defaultValue)
  }

  return (
    <RadixSelect.Root {...rootProps}>
      <RadixSelect.Trigger
        ref={ref}
        id={id}
        className={triggerClass}
        aria-label={ariaLabel}
        style={style}
        {...rest}
      >
        <RadixSelect.Value placeholder={placeholder} />
        <RadixSelect.Icon className="ui-select-icon" aria-hidden="true">
          <ChevronDown size={14} />
        </RadixSelect.Icon>
      </RadixSelect.Trigger>
      <RadixSelect.Portal>
        <RadixSelect.Content className="ui-select-content" position="popper" sideOffset={4}>
          <RadixSelect.Viewport className="ui-select-viewport">
            {children || options.map((opt) => (
              <RadixSelect.Item
                key={String(opt.value)}
                value={toRadixValue(opt.value)}
                className="ui-select-item"
                disabled={opt.disabled}
              >
                <RadixSelect.ItemText>{opt.label}</RadixSelect.ItemText>
                <RadixSelect.ItemIndicator className="ui-select-item-indicator">
                  <Check size={14} strokeWidth={2.5} />
                </RadixSelect.ItemIndicator>
              </RadixSelect.Item>
            ))}
          </RadixSelect.Viewport>
        </RadixSelect.Content>
      </RadixSelect.Portal>
    </RadixSelect.Root>
  )
})

export default Select

function SelectItem({ className = '', children, ...props }) {
  return (
    <RadixSelect.Item className={['ui-select-item', className].filter(Boolean).join(' ')} {...props}>
      <RadixSelect.ItemText>{children}</RadixSelect.ItemText>
      <RadixSelect.ItemIndicator className="ui-select-item-indicator">
        <Check size={14} strokeWidth={2.5} />
      </RadixSelect.ItemIndicator>
    </RadixSelect.Item>
  )
}

function SelectGroup({ className = '', ...props }) {
  return <RadixSelect.Group className={className} {...props} />
}

function SelectLabel({ className = '', ...props }) {
  return (
    <RadixSelect.Label
      className={['ui-select-label-group', className].filter(Boolean).join(' ')}
      {...props}
    />
  )
}

export { SelectItem, SelectGroup, SelectLabel }
export const SelectTrigger = RadixSelect.Trigger
export const SelectValue = RadixSelect.Value
export const SelectContent = RadixSelect.Content
export const SelectSeparator = RadixSelect.Separator
