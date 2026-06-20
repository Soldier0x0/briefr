import { useRef } from 'react'
import './AssetWarning.css'

const WARNING_TEXT = `// BEFORE YOU ENTER YOUR ENVIRONMENT

Your asset profile is sensitive data.
BRIEFR keeps it in this browser session only
and does not save it to browser storage.

To score CVE exposure, product and version
data is sent to POST /api/cves/match when
you apply a profile. It is not stored on
the server after matching.

When you close this tab your profile is gone.
Use the export option to save it as a local
file and reload it next visit. Store that file
as you would any sensitive document.

For maximum security:
→ Use a dedicated browser profile for security
  tooling with no personal extensions installed
→ Do not load a real asset profile on shared
  or untrusted computers
→ BRIEFR cannot protect against malicious
  browser extensions. This is a browser
  security boundary, not a BRIEFR limitation.

Recommended: Chrome Profile dedicated to
security tooling, zero extensions.`

export default function AssetWarning({ onAccept, onUpload, onSkip, onClose }) {
  const fileRef = useRef(null)

  function handlePick() {
    fileRef.current?.click()
  }

  async function handleFile(e) {
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = ''
    if (onUpload) {
      try {
        await onUpload(file)
      } catch {
        alert('Failed to load profile: Invalid or corrupted file.')
      }
    }
  }

  return (
    <div className="asset-modal-overlay" role="presentation" onClick={onClose}>
      <div
        className="asset-modal asset-warning"
        role="dialog"
        aria-modal="true"
        aria-labelledby="asset-warning-title"
        onClick={e => e.stopPropagation()}
      >
        <pre id="asset-warning-title" className="asset-warning-text mono">{WARNING_TEXT}</pre>
        <div className="asset-warning-actions">
          <button type="button" className="asset-btn asset-btn-primary mono" onClick={onAccept}>
            I understand — Set up my profile
          </button>
          <button type="button" className="asset-btn asset-btn-primary mono" onClick={handlePick}>
            Upload my profile
          </button>
          <button type="button" className="asset-btn asset-btn-ghost mono" onClick={onSkip}>
            Skip — show all CVEs
          </button>
        </div>
        <input
          ref={fileRef}
          type="file"
          accept="application/json,.json"
          className="asset-file-input"
          tabIndex={-1}
          onChange={handleFile}
        />
      </div>
    </div>
  )
}
