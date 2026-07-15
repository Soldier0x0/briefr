import Skeleton from './Skeleton.jsx'

/** Default multi-line placeholder when AsyncState has no custom skeleton (E7-2). */
export default function SkeletonStack({ lines = 3, block = true, className = '' }) {
  const widths = ['42%', '100%', '72%', '88%', '56%']
  return (
    <div className={`ui-skeleton-stack${className ? ` ${className}` : ''}`} role="status" aria-label="Loading">
      {Array.from({ length: lines }).map((_, index) => (
        <Skeleton key={index} variant="text" style={{ width: widths[index % widths.length] }} />
      ))}
      {block && <Skeleton variant="block" className="ui-skeleton-stack-block" />}
    </div>
  )
}
