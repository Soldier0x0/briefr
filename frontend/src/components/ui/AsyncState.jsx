import ErrorState from './ErrorState.jsx'
import EmptyState from './EmptyState.jsx'
import Skeleton from './Skeleton.jsx'
import SkeletonStack from './SkeletonStack.jsx'

/**
 * @param {object} props
 * @param {boolean} [props.loading=false]
 * @param {boolean} [props.refreshing=false]
 * @param {Error|string|null} [props.error]
 * @param {() => void} [props.onRetry]
 * @param {boolean} [props.empty=false]
 * @param {string} [props.emptyTitle]
 * @param {React.ReactNode} [props.emptyAction]
 * @param {React.ReactNode} [props.skeleton]
 * @param {React.ReactNode|((data: *) => React.ReactNode)} [props.children]
 * @param {*} [props.data] - Passed to function-as-children.
 */
export default function AsyncState({
  loading = false,
  refreshing = false,
  error = null,
  onRetry,
  empty = false,
  emptyTitle = 'No data',
  emptyAction,
  skeleton,
  children,
  data,
  ...rest
}) {
  if (loading && !refreshing) {
    return (
      <div role="status" aria-live="polite" {...rest}>
        {skeleton || <SkeletonStack />}
      </div>
    )
  }

  if (error && empty) {
    return <ErrorState error={error} onRetry={onRetry} {...rest} />
  }

  if (empty) {
    return <EmptyState title={emptyTitle} action={emptyAction} {...rest} />
  }

  const body = typeof children === 'function' ? children(data) : children

  return (
    <div
      className={`ui-async-body${refreshing ? ' ui-async-body--refreshing' : ''}`}
      aria-busy={refreshing || undefined}
      {...rest}
    >
      {body}
    </div>
  )
}

export { Skeleton }
