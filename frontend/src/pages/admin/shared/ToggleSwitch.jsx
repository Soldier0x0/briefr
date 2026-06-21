export default function ToggleSwitch({ on, onChange }) {
  return (
    <div className="admin-toggle-wrap admin-toggle-wrap-onoff">
      <input type="checkbox" role="switch" aria-checked={on} checked={on} onChange={e => onChange(e.target.checked)} />
      <span className="admin-toggle-slider" />
    </div>
  )
}
