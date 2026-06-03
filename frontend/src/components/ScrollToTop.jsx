import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import './ScrollToTop.css'

const HIDDEN_PATHS = ['/privacy', '/terms', '/guide']
const SHOW_AFTER_VIEWPORTS = 3

export default function ScrollToTop() {
  const { pathname } = useLocation()
  const [visible, setVisible] = useState(false)

  const hidden = HIDDEN_PATHS.some(p => pathname === p || pathname.startsWith(`${p}/`))

  useEffect(() => {
    if (hidden) {
      setVisible(false)
      return
    }

    function onScroll() {
      const threshold = window.innerHeight * SHOW_AFTER_VIEWPORTS
      setVisible(window.scrollY > threshold)
    }

    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [hidden])

  if (hidden) return null

  function handleClick() {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <button
      type="button"
      className={`scroll-to-top mono${visible ? ' scroll-to-top-visible' : ''}`}
      onClick={handleClick}
      aria-label="Scroll to top of page"
      tabIndex={visible ? 0 : -1}
    >
      ↑
    </button>
  )
}
