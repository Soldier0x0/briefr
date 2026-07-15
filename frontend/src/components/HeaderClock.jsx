import { useState, useEffect, useRef } from 'react'
import {
  COMMON_TIMEZONES,
  formatTime,
  getTimezone,
  getTzAbbr,
  getTzOffsetLabel,
  setTimezone as persistTimezone,
} from '../utils/timezone.js'
import './Header.css'

export default function HeaderClock({ className = '', onTimezoneChange }) {
  const [now, setNow] = useState(new Date())
  const [tz, setTz] = useState(() => getTimezone())
  const [popoverOpen, setPopoverOpen] = useState(false)
  const [search, setSearch] = useState('')
  const popoverRef = useRef(null)

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    function onDown(e) {
      if (popoverOpen && popoverRef.current && !popoverRef.current.contains(e.target)) {
        setPopoverOpen(false)
        setSearch('')
      }
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [popoverOpen])

  useEffect(() => {
    const onTz = (e) => setTz(e.detail)
    const onLoaded = (e) => setTz(e.detail?.timezone || getTimezone())
    window.addEventListener('briefr-timezone-change', onTz)
    window.addEventListener('briefr-preferences-loaded', onLoaded)
    return () => {
      window.removeEventListener('briefr-timezone-change', onTz)
      window.removeEventListener('briefr-preferences-loaded', onLoaded)
    }
  }, [])

  function selectTz(newTz) {
    setTz(newTz)
    persistTimezone(newTz)
    if (onTimezoneChange) onTimezoneChange(newTz)
    setPopoverOpen(false)
    setSearch('')
  }

  const utcTime = formatTime(now, 'UTC')
  const localTime = tz !== 'UTC' ? formatTime(now, tz) : null
  const tzAbbr = tz !== 'UTC' ? getTzAbbr(tz, now) : null

  const q = search.toLowerCase().trim()
  const filtered = q
    ? COMMON_TIMEZONES.filter((t) =>
        t.tz.toLowerCase().includes(q)
        || t.search.includes(q)
        || getTzAbbr(t.tz, now).toLowerCase().includes(q)
        || getTzOffsetLabel(t.tz, now).includes(q),
      )
    : COMMON_TIMEZONES

  return (
    <div className={`tz-wrap${className ? ` ${className}` : ''}`} ref={popoverRef}>
      <button
        type="button"
        className="header-clock-btn"
        onClick={() => setPopoverOpen((v) => !v)}
        aria-label="Select timezone — currently showing time in selected timezone"
        aria-expanded={popoverOpen}
      >
        {localTime && tzAbbr ? (
          <>
            <span className="clock-local">{localTime} {tzAbbr}</span>
            <span className="clock-sep">  /  </span>
            <span className="clock-utc">{utcTime} UTC</span>
          </>
        ) : (
          <span className="clock-utc">{utcTime} UTC</span>
        )}
      </button>

      {popoverOpen && (
        <div className="tz-popover" role="dialog" aria-label="Timezone selector">
          <input
            type="search"
            className="tz-search mono"
            placeholder="Search timezone..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            autoFocus
            aria-label="Search timezones"
          />
          <ul className="tz-list" role="listbox" aria-label="Available timezones">
            {filtered.map((t) => {
              const abbr = getTzAbbr(t.tz, now)
              const offset = getTzOffsetLabel(t.tz, now)
              const time = formatTime(now, t.tz)
              const active = tz === t.tz
              return (
                <li
                  key={t.tz}
                  className={`tz-item${active ? ' tz-item-active' : ''}`}
                  role="option"
                  aria-selected={active}
                  onClick={() => selectTz(t.tz)}
                >
                  <span className="tz-item-abbr mono">{abbr}</span>
                  <span className="tz-item-offset mono">{offset}</span>
                  <span className="tz-item-time mono">{time}</span>
                  <span className="tz-item-name">{t.tz}</span>
                </li>
              )
            })}
            {filtered.length === 0 && (
              <li className="tz-empty mono">No match for &quot;{search}&quot;</li>
            )}
          </ul>
        </div>
      )}
    </div>
  )
}
