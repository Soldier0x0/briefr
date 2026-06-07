import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import { AssetProfileProvider } from './context/AssetProfileContext.jsx'
import './App.css'
import './theme/light-theme.css'

try {
  if (localStorage.getItem('briefr_theme') === 'light') {
    document.documentElement.setAttribute('data-theme', 'light')
  }
} catch {}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <AssetProfileProvider>
        <App />
      </AssetProfileProvider>
    </BrowserRouter>
  </React.StrictMode>
)
