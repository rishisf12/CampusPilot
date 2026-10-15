import { Suspense } from 'react';
import { ModuleErrorBoundary } from '@shared/components/ModuleErrorBoundary';

function ModuleLoading() {
  return (
    <div className="flex justify-center py-12">
      <div className="w-8 h-8 border-4 border-primary-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

/**
 * Faculty Routes - placeholder for future faculty module.
 *
 * Currently empty - will be implemented when faculty features are added.
 */
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
              Coming soon â€” faculty features are not yet implemented.
            </p>
          </div>
        </div>
      </Suspense>
    </ModuleErrorBoundary>
  );
}
