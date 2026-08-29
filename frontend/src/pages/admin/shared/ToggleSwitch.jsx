import { Switch } from '../../../components/ui/index.js'

export default function ToggleSwitch({ on, onChange, disabled = false, label, ...rest }) {
  const ariaLabel = label || rest['aria-label']
  return (
    <Switch
      checked={on}
      onCheckedChange={onChange}
      disabled={disabled}
      {...rest}
      aria-label={ariaLabel}
    />
  )
}
