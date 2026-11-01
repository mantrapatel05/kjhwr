import { Component } from 'react';

export function Skeleton({ variant = 'block', label = 'Loading' }) {
  return (
    <div className={`skeleton skeleton--${variant}`} role="status">
      <span className="sr-only">{label}</span>
    </div>
  );
}

export function ErrorState({ title = 'This could not be loaded', error, onRetry }) {
  return (
    <div className="state state--error" role="alert">
      <h2 className="state__title">{title}</h2>
      <p className="state__body">{error?.message ?? 'Something unexpected happened.'}</p>
      {onRetry && (
        <button type="button" className="button button--primary" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, children }) {
  return (
    <div className="state">
      <h2 className="state__title">{title}</h2>
      <div className="state__body">{children}</div>
    </div>
  );
}

/** Renders loading, error or success for a useApi() result. */
export function Async({ state, skeleton, errorTitle, children }) {
  if (state.status === 'success') return children(state.data);
  if (state.status === 'error') {
    return <ErrorState title={errorTitle} error={state.error} onRetry={state.retry} />;
  }
  return skeleton;
}

export class ErrorBoundary extends Component {
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
        <ErrorState
          title="This page failed to display"
          error={new Error('An unexpected error occurred while drawing this page. Reload to try again.')}
          onRetry={() => window.location.reload()}
        />
      );
    }
    return this.props.children;
  }
}
