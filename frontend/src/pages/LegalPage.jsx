import { Link, useNavigate } from 'react-router-dom'
import Header from '../components/Header.jsx'
import './LegalPage.css'

export default function LegalPage({ title, subtitle, children }) {
  const navigate = useNavigate()

  return (
    <div className="app">
      {/* Logo navigates home; About and nav tabs hidden on legal pages */}
      <Header
        activeTab={null}
        onTabChange={() => {}}
        onAboutOpen={() => navigate('/')}
      />
      <main className="legal-main">
        <div className="legal-content">
          <Link to="/" className="legal-back mono" aria-label="Back to CVE feed">
            &larr; BACK
          </Link>
          <h1 className="legal-title">{title}</h1>
          {subtitle && (
            <p className="legal-subtitle mono">{subtitle}</p>
          )}
          <div className="legal-body">
            {children}
          </div>
          <p className="legal-copyright mono">
            &copy; 2026 BRIEFR &middot; Proprietary Software &middot; All Rights Reserved
          </p>
        </div>
      </main>
    </div>
  )
}
