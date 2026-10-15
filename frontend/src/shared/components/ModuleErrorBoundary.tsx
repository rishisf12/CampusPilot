import { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Button, Card, IconTile } from '@/components/ui';

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
        <div
          className="min-h-screen flex items-center justify-center px-4"
          style={{ background: 'var(--cp-bg)' }}
        >
          <div className="max-w-md w-full text-center">
            <Card className="space-y-4">
              <IconTile hue="coral" size={48} className="mx-auto">
                <AlertTriangle
                  size={24}
                  strokeWidth={2}
                  aria-hidden
                  style={{ color: 'currentColor' }}
                />
              </IconTile>
              <h2 className="text-lg font-semibold" style={{ color: 'var(--cp-text)' }}>
                Something went wrong
              </h2>
              <p className="text-sm" style={{ color: 'var(--cp-muted)' }}>
                This module encountered an error and couldn&apos;t load. The rest of the app is
                still working.
              </p>
              <details className="text-left">
                <summary className="text-sm cursor-pointer" style={{ color: 'var(--cp-muted)' }}>
                  Error details
                </summary>
                <pre
                  className="mt-2 p-3 rounded-xl text-xs overflow-auto max-h-48 neu-inset"
                  style={{ color: 'var(--cp-text)' }}
                >
                  {this.state.error?.message}
                  {this.state.error?.stack}
                </pre>
              </details>
              <Button
                type="button"
                variant="primary"
                size="sm"
                icon={
                  <RefreshCw
                    size={16}
                    strokeWidth={2}
                    aria-hidden
                    style={{ color: 'currentColor' }}
                  />
                }
                onClick={() => window.location.reload()}
              >
                Reload page
              </Button>
            </Card>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
