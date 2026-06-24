import './Hero.css'

export default function Hero() {
  return (
    <section className="hero" aria-label="BRIEFR brief">
      <h1 className="hero-heading">
        <em>What broke overnight.</em>
      </h1>
      <p className="hero-sub">
        Your morning snapshot: new CVEs, KEV additions, and what changed — scoped to My Stack when you set it up.
      </p>
    </section>
  )
}
