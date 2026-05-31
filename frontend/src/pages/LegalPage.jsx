import { Link } from 'react-router-dom'
import Header from '../components/Header.jsx'
import './LegalPage.css'

export default function LegalPage({ title, subtitle, children }) {
  return (
    <div className="app">
      <Header activeTab={null} onTabChange={() => {}} onAboutOpen={() => {}} />
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
        </div>
      </main>
    </div>
  )
}
