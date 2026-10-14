import { Suspense, lazy, useEffect, useState } from 'react';
import { useAuth } from '@shared/auth/AuthWrapper';
import { healthApi } from '@/api';
import ErrorBanner from '@shared/components/ErrorBanner';
import { ModuleErrorBoundary } from '@shared/components/ModuleErrorBoundary';
import { Sidebar } from '@shared/components/Sidebar';

/** Lazy-loaded features */
const AdminPanel = lazy(() => import('./features/admin/AdminPanel'));
const Monitoring = lazy(() => import('./features/monitoring/Monitoring'));
const Profile = lazy(() => import('@shared/features/profile/Profile'));

function ModuleLoading() {
  return (
    <div className="flex justify-center py-12">
      <div className="w-8 h-8 border-4 border-primary-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

/** Poll the backend so the header dot reflects real connectivity. */
function useBackendStatus() {
  const [online, setOnline] = useState(false);
  useEffect(() => {
    let cancelled = false;
    const ping = async () => {
      try {
        await healthApi.check();
        if (!cancelled) setOnline(true);
      } catch {
        if (!cancelled) setOnline(false);
      }
    };
    ping();
    const timer = setInterval(ping, 30000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);
  return online;
}

interface AdminTab {
  id: string;
  label: string;
}

/**
 * Admin Routes - defines all routes for admin users.
 *
 * Sections: Feedback Responses, Web Monitoring, Android Monitoring
 * Profile is accessed via sidebar
 */
export function AdminRoutes() {
  const { offline } = useAuth();
  const online = useBackendStatus();
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [adminTab, setAdminTab] = useState('responses');
  // Sidebar open state
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Admin sub-tabs (Profile removed - accessed via sidebar)
  const ADMIN_TABS: AdminTab[] = [
    { id: 'responses', label: 'Feedback Responses' },
    { id: 'web-monitoring', label: 'Web App Monitoring' },
    { id: 'android-monitoring', label: 'Android App Monitoring' },
  ];

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Single static header, flush at the top, never scrolls away */}
      <header className="sticky top-0 z-40 bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Top row: brand + sidebar toggle + status indicator */}
          <div className="flex items-center justify-between gap-4 h-16">
            {/* Brand */}
            <div className="flex items-center gap-3 shrink-0">
              <div className="leading-tight">
                <p className="text-lg font-bold text-primary-500">essential</p>
                <p className="text-[10px] tracking-widest font-semibold text-cyan-600 whitespace-nowrap">
                  YOUR CAMPUS ASSISTANT
                </p>
              </div>
            </div>

            <span className="px-3 py-1.5 text-sm font-semibold text-primary-600 bg-primary-50 rounded-lg whitespace-nowrap">
              Admin
            </span>

            {/* Right side: status indicator + sidebar toggle */}
            <div className="flex items-center gap-3 shrink-0">
              <span
                className={`w-2.5 h-2.5 rounded-full ${online ? 'bg-success-500' : 'bg-danger-500'}`}
                title={online ? 'Backend connected' : 'Backend offline'}
                aria-label={online ? 'Backend connected' : 'Backend offline'}
              />
              {/* Sidebar Toggle Button in header */}
              <button
                type="button"
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="w-10 h-10 rounded-lg bg-gray-50 hover:bg-gray-100 flex items-center justify-center transition-colors"
                aria-label={sidebarOpen ? 'Close menu' : 'Open menu'}
                aria-expanded={sidebarOpen}
              >
                <svg
                  className="w-6 h-6 text-gray-600"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <line x1="3" y1="12" x2="21" y2="12" />
                  <line x1="3" y1="6" x2="21" y2="6" />
                  <line x1="3" y1="18" x2="21" y2="18" />
                </svg>
              </button>
            </div>
          </div>

          {/* Second row: Admin sub-tabs */}
          <div className="flex items-center justify-center gap-1 pb-4">
            <nav className="flex items-center gap-1" aria-label="Admin sections">
              {ADMIN_TABS.map(item => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setAdminTab(item.id)}
                  aria-current={adminTab === item.id ? 'page' : undefined}
                  className={`px-3 py-1.5 text-sm font-medium whitespace-nowrap rounded-full transition-colors ${
                    adminTab === item.id
                      ? 'bg-primary-500 text-white'
                      : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </nav>
          </div>
        </div>
      </header>

      {/* Sidebar */}
      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onSectionChange={setAdminTab}
      />

      {/* Content, centred */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <ModuleErrorBoundary moduleName="admin">
          {offline && !online && (
            <ErrorBanner
              message="Backend offline - start it with: uvicorn main:app --port 8000"
              onDismiss={() => setConnectionError(null)}
              className="mb-4"
            />
          )}
          {connectionError && (
            <ErrorBanner
              message={connectionError}
              onDismiss={() => setConnectionError(null)}
              className="mb-4"
            />
          )}

          <Suspense fallback={<ModuleLoading />}>
            {adminTab === 'responses' && <AdminPanel onError={setConnectionError} />}
            {adminTab === 'web-monitoring' && <Monitoring platformGroup="Web App Monitoring" />}
            {adminTab === 'android-monitoring' && (
              <Monitoring platformGroup="Android App Monitoring" />
            )}
            {adminTab === 'profile' && <Profile />}
          </Suspense>
        </ModuleErrorBoundary>
      </main>

      {/* Single footer */}
      <footer className="bg-white border-t border-gray-200 py-4">
        <div className="max-w-7xl mx-auto px-4 text-center text-xs text-gray-500">
          essential &mdash; your campus assistant
        </div>
      </footer>
    </div>
  );
}
