/**
 * Faculty Routes — includes OppFeed opportunity feed.
 */
import { Suspense, lazy } from 'react';
import { ModuleErrorBoundary } from '@shared/components/ModuleErrorBoundary';

function ModuleLoading() {
  return (
    <div className="flex justify-center py-12">
      <div className="w-8 h-8 border-4 border-primary-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

const OppFeedList = lazy(() => import('./features/oppfeed/OppFeedList'));

export function FacultyRoutes() {
  return (
    <ModuleErrorBoundary moduleName="faculty">
      <Suspense fallback={<ModuleLoading />}>
        <div
          className="min-h-screen flex items-center justify-center neu-raised m-4"
          style={{ background: 'var(--cp-bg)' }}
        >
          <div className="text-center">
            <h1 className="text-2xl font-semibold" style={{ color: 'var(--cp-text)' }}>
              Faculty Module
            </h1>
            <p className="mt-2" style={{ color: 'var(--cp-muted)' }}>
              OppFeed Opportunities
            </p>
            <OppFeedList />
          </div>
        </div>
      </Suspense>
    </ModuleErrorBoundary>
  );
}
