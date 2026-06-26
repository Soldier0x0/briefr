import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import AppErrorBoundary from './components/AppErrorBoundary.jsx'
import { AssetProfileProvider } from './context/AssetProfileContext.jsx'
import { AuthProvider } from './context/AuthContext.jsx'
import { fetchAndCacheRiskWeights } from './scoring/riskScore.js'
import { applyDisplayPrefs } from './utils/displayPrefs.js'
// Self-hosted fonts — no runtime requests to Google (privacy posture, offline
// capability, no FOUT on cold loads).
import '@fontsource/dm-sans/300.css'
import '@fontsource/dm-sans/400.css'
import '@fontsource/dm-sans/400-italic.css'
import '@fontsource/dm-sans/500.css'
import '@fontsource/dm-serif-display/400.css'
import '@fontsource/dm-serif-display/400-italic.css'
import '@fontsource/ibm-plex-mono/300.css'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'
import './theme/design-system.css'
import './App.css'

// Warm the risk-weights cache from the backend once at startup.
// Falls back to bundled constants on any error — no user impact.
fetchAndCacheRiskWeights().catch(() => {})
applyDisplayPrefs()

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AppErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <AssetProfileProvider>
            <App />
          </AssetProfileProvider>
        </AuthProvider>
      </BrowserRouter>
    </AppErrorBoundary>
  </React.StrictMode>
)
