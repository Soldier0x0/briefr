import { Switch } from '../../../components/ui/index.js'

export default function ToggleSwitch({ on, onChange, disabled = false, ...rest }) {
  return (
    <Switch
      checked={on}
      onCheckedChange={onChange}
      disabled={disabled}
      {...rest}
    />
  )
}
