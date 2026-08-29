import ToggleSwitch from '../pages/admin/shared/ToggleSwitch.jsx'

export default function AssetRememberToggle({
  enabled,
  onChange,
  disabled = false,
}) {
  return (
    <label className="asset-remember-toggle mono">
      <ToggleSwitch on={!!enabled} onChange={onChange} disabled={disabled} label="Remember My Stack on this server" />
      <span>
        Remember My Stack on this server
        <span className="asset-remember-hint">
          Off by default on shared terminals — session only until you close the tab.
          When on, inventory is stored under your account and restored on sign-in.
        </span>
      </span>
    </label>
  )
}
