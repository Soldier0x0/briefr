import { Link } from 'react-router-dom'
import Header from '../components/Header.jsx'
import './LegalPage.css'

export default function LegalPage({ title, lastUpdated, sections }) {
  return (
    <div className="app">
      <Header activeTab={null} onTabChange={() => {}} onAboutOpen={() => {}} />
      <main className="legal-main">
        <div className="legal-content">
          <Link to="/" className="legal-back mono" aria-label="Back to CVE feed">
            &larr; Back to feed
          </Link>

          <h1 className="legal-title">{title}</h1>
          {lastUpdated && (
            <p className="legal-updated mono">Last updated: {lastUpdated}</p>
          )}

          {sections.map((section, i) => (
            <section key={i} className="legal-section">
              {section.heading && (
                <h2 className="legal-heading">{section.heading}</h2>
              )}
              {section.paragraphs.map((para, j) => (
                <p key={j} className="legal-para">{para}</p>
              ))}
              {section.list && (
                <ul className="legal-list">
                  {section.list.map((item, k) => (
                    <li key={k}>{item}</li>
                  ))}
                </ul>
              )}
            </section>
          ))}
        </div>
      </main>
    </div>
  )
}
