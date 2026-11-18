import { Component } from 'react';

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <main className="page-content" role="alert">
          <div className="card">
            <h1 className="page-title">Something went wrong</h1>
            <p className="page-subtitle">{this.state.error.message || 'Unexpected UI error'}</p>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => this.setState({ error: null })}
            >
              Try again
            </button>
          </div>
        </main>
      );
    }
    return this.props.children;
  }
}
