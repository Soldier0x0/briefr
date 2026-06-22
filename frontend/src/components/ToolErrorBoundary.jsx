import { Component } from 'react'
import { AlertTriangle } from 'lucide-react'

// Class component is required here - React has no hook-based error boundary.
// Scopes a render-time exception to one tab/tool/overlay instead of letting
// it propagate to the root AppErrorBoundary and reset the whole session
// (filters, drawer, other tabs' state). Mirrors pages/admin/shared/ErrorBoundary.jsx.
export default class ToolErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('Tool render error:', error, info)
  }

  handleRetry = () => {
    this.setState({ error: null })
    this.props.onReset?.()
  }

  render() {
    if (this.state.error) {
      return (
        <div className="tool-crash">
          <AlertTriangle className="tool-crash-icon" size={18} strokeWidth={2} />
          <div className="tool-crash-message">
            {this.props.label ? `${this.props.label} failed to render: ` : 'This failed to render: '}
            {String(this.state.error.message || this.state.error)}
          </div>
          <button type="button" className="tool-crash-retry" onClick={this.handleRetry}>
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
