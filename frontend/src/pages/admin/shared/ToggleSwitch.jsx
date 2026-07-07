export default function ToggleSwitch({ on, onChange, disabled = false }) {
  return (
    <div className={`admin-toggle-wrap admin-toggle-wrap-onoff${disabled ? ' admin-toggle-wrap--disabled' : ''}`}>
      <input type="checkbox" role="switch" aria-checked={on} checked={on} disabled={disabled} onChange={e => onChange(e.target.checked)} />
      <span className="admin-toggle-slider" />
    </div>
  )
}
