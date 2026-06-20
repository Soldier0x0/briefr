import { Component } from 'react'

// Class component is required here - React has no hook-based error boundary.
// Wraps each admin page's render so a render-time exception (e.g. malformed API
// response) shows a recoverable block instead of crashing the whole admin panel.
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('Admin page render error:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="admin-empty" style={{ color: 'var(--red)' }}>
          This page failed to render: {String(this.state.error.message || this.state.error)}
          <button
            className="admin-btn admin-btn-ghost"
            style={{ marginLeft: '0.75rem', fontSize: '0.75rem' }}
            onClick={() => this.setState({ error: null })}
          >
            Retry
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
