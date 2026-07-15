import { useId } from 'react'
import * as RadixSlider from '@radix-ui/react-slider'
import './ui.css'

/**
 * Radix-backed slider primitive (E3-6).
 * @param {object} props
 * @param {number} [props.value]
 * @param {number} [props.defaultValue]
 * @param {(value: number) => void} [props.onValueChange]
 * @param {(value: number) => void} [props.onChange] Alias for onValueChange
 * @param {number} [props.min=0]
 * @param {number} [props.max=100]
 * @param {number} [props.step=1]
 * @param {boolean} [props.disabled]
 * @param {string} [props.id]
 * @param {string} [props.className]
 * @param {string} [props.label]
 * @param {string} [props.valueSuffix] Shown beside the current value (e.g. "px")
 * @param {string} [props['aria-label']]
 */
export default function Slider({
  value,
  defaultValue,
  onValueChange,
  onChange,
  min = 0,
  max = 100,
  step = 1,
  disabled = false,
  id,
  className = '',
  label,
  valueSuffix = '',
  'aria-label': ariaLabel,
  ...rest
}) {
  const defaultId = useId()
  const sliderId = id || defaultId

  const handleChange = (values) => {
    const next = values[0]
    onValueChange?.(next)
    onChange?.(next)
  }

  const rootProps = {
    min,
    max,
    step,
    disabled,
    onValueChange: handleChange,
    ...rest,
  }

  if (value !== undefined) {
    rootProps.value = [value]
  }
  if (defaultValue !== undefined) {
    rootProps.defaultValue = [defaultValue]
  }

  const displayValue = value ?? defaultValue ?? min
  const valueLabel = valueSuffix ? `${displayValue}${valueSuffix}` : String(displayValue)

  const control = (
    <RadixSlider.Root
      id={sliderId}
      className={['ui-slider', className].filter(Boolean).join(' ')}
      aria-label={ariaLabel || (label ? undefined : 'Slider')}
      {...rootProps}
    >
      <RadixSlider.Track className="ui-slider-track">
        <RadixSlider.Range className="ui-slider-range" />
      </RadixSlider.Track>
      <RadixSlider.Thumb className="ui-slider-thumb" aria-label={ariaLabel || label || 'Slider thumb'} />
    </RadixSlider.Root>
  )

  if (!label) return control

  return (
    <div className="ui-slider-field">
      <div className="ui-slider-header">
        <label className="ui-slider-label" htmlFor={sliderId}>{label}</label>
        <span className="ui-slider-value mono" aria-hidden="true">{valueLabel}</span>
      </div>
      {control}
    </div>
  )
}

export const SliderTrack = RadixSlider.Track
export const SliderRange = RadixSlider.Range
export const SliderThumb = RadixSlider.Thumb
