import { ingestLogUrl } from '../../utils/adminLinks.js'
import Button from './Button.jsx'

function errorMessage(error) {
  if (!error) return 'Request could not be completed.'
  if (typeof error === 'string') return error
  return error.message || 'Request could not be completed.'
}

/**
 * @param {object} props
 * @param {Error|string|null} props.error
 * @param {() => void} [props.onRetry]
 * @param {boolean} [props.compact=false]
 * @param {string} [props.logHref] - Override log viewer href (router-free).
 */
export default function ErrorState({ error, onRetry, compact = false, logHref, ...rest }) {
  const requestId = error && typeof error === 'object' ? error.requestId : null
  const href = logHref || (requestId ? ingestLogUrl({ level: 'ERROR', requestId }) : null)
  const classes = ['ui-error', compact ? 'ui-error--compact' : ''].filter(Boolean).join(' ')

  return (
    <div className={classes} role="alert" {...rest}>
      <span className="ui-error-message">
        {errorMessage(error)}
        {requestId && href && (
          <>
            {' '}
            (<a className="ui-error-ref" href={href}>
              ref: {requestId}
            </a>)
          </>
        )}
      </span>
      {onRetry && (
        <Button variant="ghost" size="sm" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  )
}
