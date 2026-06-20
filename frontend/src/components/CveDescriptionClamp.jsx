import './CveDescriptionClamp.css'

const DEFAULT_MAX_CHARS = 280

/**
 * Truncate CVE description text with a line clamp (used by CVECard).
 * @param {{ text: string, maxLines?: number, maxChars?: number, className?: string }} props
 */
export default function CveDescriptionClamp({
  text,
  maxLines = 2,
  maxChars = DEFAULT_MAX_CHARS,
  className = '',
}) {
  if (!text) return null

  const trimmed =
    text.length > maxChars ? `${text.slice(0, maxChars).trimEnd()}…` : text

  return (
    <p
      className={`cve-description-clamp${className ? ` ${className}` : ''}`}
      style={{ WebkitLineClamp: maxLines }}
    >
      {trimmed}
    </p>
  )
}
