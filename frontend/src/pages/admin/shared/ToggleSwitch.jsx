import { Switch } from '../../../components/ui/index.js'

export default function ToggleSwitch({ on, onChange, disabled = false }) {
  return (
    <Switch
      checked={on}
      onCheckedChange={onChange}
      disabled={disabled}
      aria-label="Toggle"
    />
  )
}
