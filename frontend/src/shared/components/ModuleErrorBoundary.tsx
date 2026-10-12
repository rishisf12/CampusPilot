import { Component, ErrorInfo, ReactNode } from 'react';

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  moduleName?: string;
}

/**
 * Error boundary to catch rendering errors in a module subtree.
 *
 * When a module crashes, this prevents the entire app from going white.
 * The rest of the UI (header, other modules) stays functional.
 *
 * Usage:
 *   <ModuleErrorBoundary moduleName="student-ug">
 *     <StudentUGRoutes />
 *   </ModuleErrorBoundary>
 */
export class ModuleErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ error, errorInfo });
    this.props.onError?.(error, errorInfo);
    // Log to console in dev, could send to error tracking service in prod
    console.error('[ModuleErrorBoundary]', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
          <div className="max-w-md text-center">
            <div className="bg-white border border-gray-200 rounded-xl p-6">
              <div className="w-12 h-12 mx-auto mb-4 bg-danger-50 rounded-full flex items-center justify-center">
                <svg
                  className="w-6 h-6 text-danger-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                  />
                </svg>
              </div>
              <h2 className="text-lg font-semibold text-gray-900">Something went wrong</h2>
              <p className="mt-2 text-sm text-gray-600">
                This module encountered an error and couldn't load. The rest of the app is still
                working.
              </p>
              <details className="mt-4 text-left">
                <summary className="text-sm text-gray-500 cursor-pointer">Error details</summary>
                <pre className="mt-2 p-3 bg-gray-100 rounded text-xs text-gray-700 overflow-auto max-h-48">
                  {this.state.error?.message}
                  {this.state.error?.stack}
                </pre>
              </details>
              <button onClick={() => window.location.reload()} className="mt-4 btn-primary text-sm">
                Reload page
              </button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
