import { Link, useNavigate } from 'react-router-dom'
import Header from '../components/Header.jsx'
import './LegalPage.css'

export default function LegalPage({ title, subtitle, children }) {
  const navigate = useNavigate()

  return (
    <div className="app">
      <Header
        activeTab={null}
        onTabChange={() => {}}
        onAboutOpen={() => navigate('/')}
        onLogoClick={() => navigate('/')}
      />
      <main className="legal-main">
        <div className="legal-content">
          <Link to="/" className="legal-back mono" aria-label="Back to BRIEFR home">
            &larr; BACK TO BRIEFR
          </Link>
          <h1 className="legal-title">{title}</h1>
          {subtitle && (
            <p className="legal-subtitle mono">{subtitle}</p>
          )}
          <div className="legal-body">
            {children}
          </div>
          <p className="legal-copyright mono">
            &copy; 2026 BRIEFR &middot; Licensed under the Business Source License 1.1
          </p>
        </div>
      </main>
    </div>
  )
}
