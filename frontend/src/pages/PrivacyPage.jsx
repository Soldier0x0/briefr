import LegalPage from './LegalPage.jsx'

export default function PrivacyPage() {
  return (
    <LegalPage
      title="Privacy Policy"
      subtitle="Effective July 2026 — projectjupiter.in"
    >
      <h2 className="legal-section-heading">1. What we do not collect</h2>
      <ul className="legal-ul">
        <li>No analytics (no Google Analytics, no Plausible)</li>
        <li>No IP addresses written to logs or any database</li>
        <li>No browser fingerprinting or tracking</li>
        <li>No data sold or shared with third parties</li>
      </ul>

      <h2 className="legal-section-heading">2. What we do collect</h2>

      <h3 className="legal-sub-heading">Login &amp; session cookies</h3>
      <p className="legal-p">
        BRIEFR requires sign-in for operator and analyst accounts. Analyst
        API routes reject unauthenticated requests. When you log in, the
        backend issues two httpOnly, Secure, SameSite=Strict cookies: a
        short-lived access token and a longer-lived session (refresh) token
        used to keep you signed in without re-entering your password. Neither
        cookie is readable by page JavaScript. Your account record stores
        your username and a one-way bcrypt hash of your password — never
        the password itself. Checking "Remember me" persists the session
        cookie for up to 30 days; leaving it unchecked makes it a
        session-only cookie cleared when the browser closes. Logging out, or
        an administrator revoking a session, invalidates these cookies
        immediately.
      </p>

      <h3 className="legal-sub-heading">IOC lookup cache</h3>
      <p className="legal-p">
        When you use IOC Lookup, your submitted IP address, file hash, or domain
        is sent to third-party enrichment services: VirusTotal, AbuseIPDB,
        GreyNoise (IP addresses only), and abuse.ch (MalwareBazaar for hashes and
        URLhaus for domains — one shared Auth-Key from auth.abuse.ch). The combined
        result is cached locally for up to
        6 hours to reduce API calls; GreyNoise IP results are refreshed at most
        every 1 hour. This cache stores only the IOC value and the enrichment
        result — not associated with any user or session. If you submit an
        IOC belonging to someone else (e.g. a third party's IP address), that
        value is sent to the services above under their own terms — you are
        responsible for having a legitimate reason to do so. We process these
        submissions on the basis of legitimate interest in security research
        and threat intelligence.
      </p>

      <h3 className="legal-sub-heading">Rate limiting</h3>
      <p className="legal-p">
        To prevent abuse, requests to a few endpoints (IOC lookup, refresh,
        wallboard) are throttled per requesting IP address using short-lived,
        in-memory counters (optionally shared via the database when
        multi-worker rate-limit store is enabled). The IP is held only long
        enough to enforce the limit and is never written to an application
        log line as a tracked identifier — it is discarded once the counter
        goes idle.
      </p>

      <h3 className="legal-sub-heading">Application logs</h3>
      <p className="legal-p">
        The backend logs HTTP method, path, status code, and response time
        for each request, for operational debugging. These log lines do not
        contain your IP address, User-Agent string, or query parameters.
        Structured log extras matching secret patterns are redacted.
      </p>

      <h2 className="legal-section-heading">3. Your stack profile (server)</h2>
      <p className="legal-p">
        When you are signed in, the comma-separated stack terms you enter in the
        Feed tab are stored in the application database under your user account
        (<code>user_preferences</code>) — not in browser localStorage. They are
        used to filter CVEs and, when no operator override is set, for KEV-on-stack
        webhook alerts and the wallboard tile.
      </p>
      <p className="legal-p">
        My Stack inventory (operating systems, applications, environment) is
        session-only by default on shared terminals. If you enable
        &quot;Remember on server&quot; while signed in, that inventory JSON is also
        stored under your account and restored on your next sign-in. CVE matching
        still uses <code>POST /api/cves/match</code> at apply time. A timestamp of
        your last visit may still be stored locally under <code>briefr_last_visit</code>
        to highlight new CVEs since your previous session.
      </p>

      <h2 className="legal-section-heading">4. Display preferences (server)</h2>
      <p className="legal-p">
        When you are signed in, display settings (font size, density, poll interval,
        UTC timestamps, reduced motion, scheduler table IDs) and your selected timezone
        are stored in <code>user_preferences</code> under your user account — not in
        browser localStorage. They follow you across devices on this instance.
      </p>

      <h2 className="legal-section-heading">5. Third-party services</h2>
      <ul className="legal-ul">
        <li>NVD/NIST — CVE catalog — server-side rolling sync (default hourly; configurable)</li>
        <li>CISA — Known Exploited Vulnerabilities (KEV) — server-side (default every 15 minutes)</li>
        <li>FIRST.org — EPSS scores — server-side (default every 6 hours)</li>
        <li>OSV.dev — open-source vulnerability data — server-side enrichment</li>
        <li>MITRE ATT&amp;CK / ATLAS — technique and AI-threat frameworks — server-side refresh</li>
        <li>AlienVault OTX — community pulse / campaign intel — server-side sync</li>
        <li>SigmaHQ — community Sigma detection rules mirrored into a local Postgres index (default weekly tarball sync; DRL-1.1 license retained). Detect may fall back to live GitHub search only when that index is empty</li>
        <li>Elastic detection-rules (GitHub) — on-demand community rule search when you open Detect</li>
        <li>CIRCL CVE-Search — supplemental CVE references — server-side on CVE detail load</li>
        <li>Sploitus — public exploit search per CVE — server-side when you open CVE detail (Intel tab)</li>
        <li>VirusTotal — IOC enrichment — only when you use IOC Lookup</li>
        <li>AbuseIPDB — IP reputation — only when you use IOC Lookup</li>
        <li>GreyNoise — internet scanning context for IPs — only when you use IOC Lookup (requires server API key)</li>
        <li>abuse.ch (MalwareBazaar + URLhaus) — one Auth-Key — IOC Lookup for hashes and domains</li>
        <li>Groq, Cerebras, OpenRouter, Gemini (LLM providers, tried in that failover order) — receive CVE findings, IOC values you looked up, and threat-actor names as part of a prompt — only when you click "Export PDF" (executive summary) or during scheduled product/detection-artifact extraction on newly published CVEs. If no provider is configured, these features fall back to a template with no data sent anywhere.</li>
      </ul>
      <p className="legal-p">
        Fonts are self-hosted — your browser makes no requests to Google Fonts
        or any other typography CDN.
      </p>

      <h2 className="legal-section-heading">6. Your rights</h2>
      <p className="legal-p">
        Sai Harsha Vardhan, sole operator of projectjupiter.in, is the Data
        Fiduciary for this hosted instance. Section 3 above is the complete
        list of what is persisted against your account: your username, a
        bcrypt hash of your password, your saved stack terms/inventory (only
        if you enable "Remember on server"), and your display preferences.
        Nothing else about your usage is retained. You can already view and
        change your stack terms and display preferences yourself, at any
        time, from within the app. Full account erasure — deleting the
        account row and everything tied to it — is not yet self-service; it
        is performed by the operator on request, typically within 7 days.
        You can also clear localStorage at any time, and IOC cache entries
        auto-purge after 6 hours. To request erasure, correction, or to
        raise a grievance, contact our Grievance Officer, Sai Harsha
        Vardhan, at harsha@projectjupiter.in.
      </p>

      <h2 className="legal-section-heading">7. Children</h2>
      <p className="legal-p">
        BRIEFR is a technical security tool intended for professionals and
        researchers. It is not directed at children under the age of 13.
      </p>

      <h2 className="legal-section-heading">8. License and self-hosting</h2>
      <p className="legal-p">
        BRIEFR&apos;s source code is licensed under the Apache License,
        Version 2.0 — see the Terms of Service for details. Copyright
        &copy; 2026 Sai Harsha Vardhan. This Privacy Policy describes data practices for
        the hosted instance at projectjupiter.in only. If you encounter a
        self-hosted BRIEFR instance elsewhere, its operator — not Sai Harsha
        Vardhan — is the data fiduciary for that instance, and this policy
        does not apply to it.
      </p>
    </LegalPage>
  )
}
