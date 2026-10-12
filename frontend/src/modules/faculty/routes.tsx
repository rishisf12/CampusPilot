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
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
          <div className="text-center">
            <h1 className="text-2xl font-semibold text-gray-900">Faculty Module</h1>
            <p className="text-gray-600 mt-2">
              Coming soon — faculty features are not yet implemented.
            </p>
          </div>
        </div>
      </Suspense>
    </ModuleErrorBoundary>
  );
}
