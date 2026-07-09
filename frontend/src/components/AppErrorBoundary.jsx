import { Component } from 'react'

// Class component is required here - React has no hook-based error boundary.
// Wraps the whole app so a render-time exception anywhere in the tree shows a
// recoverable screen instead of a blank white page.
export default class AppErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('Unhandled render error:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="app-crash">
          <div className="app-crash-box">
            <h1>Application error</h1>
            <p>The interface could not render. {String(this.state.error.message || this.state.error)}</p>
            <button
              type="button"
              className="app-crash-retry"
              onClick={() => this.setState({ error: null })}
            >
              Try again
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
