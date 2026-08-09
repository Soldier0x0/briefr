import './LogoMark.css'

const SIZES = {
  sm: 24,
  md: 32,
  lg: 48,
}

export default function LogoMark({ size = 'md', className = '', title, ...props }) {
  const px = SIZES[size] ?? SIZES.md
  return (
    <svg
      viewBox="0 0 48 48"
      width={px}
      height={px}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className ? `logo-mark ${className}` : 'logo-mark'}
      aria-hidden={title ? undefined : true}
      role={title ? 'img' : undefined}
      {...props}
    >
      {title ? <title>{title}</title> : null}
      <path d="M11 13v22M16 13v22" stroke="var(--border-strong)" strokeWidth="2" strokeLinecap="round" />
      <rect x="22" y="14" width="22" height="3" rx="1" fill="var(--accent-primary)" />
      <rect x="22" y="22" width="15" height="2.5" rx="1" fill="var(--text-heading)" opacity="0.75" />
      <rect x="22" y="29" width="10" height="2.5" rx="1" fill="var(--text-muted)" />
    </svg>
  )
}
