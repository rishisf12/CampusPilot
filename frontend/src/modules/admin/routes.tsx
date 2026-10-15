import { Suspense, lazy, useEffect, useState } from 'react';
import { Activity, Menu, MessageSquare, Smartphone, X } from 'lucide-react';
import { useAuth } from '@shared/auth/AuthWrapper';
import { healthApi } from '@/api';
import { Badge, Tabs } from '@/components/ui';
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
      <div
        className="w-8 h-8 border-4 border-t-transparent rounded-full animate-spin"
        style={{ borderColor: 'var(--cp-primary)', borderTopColor: 'transparent' }}
      />
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
  icon?: React.ReactNode;
  hue?: string;
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
    {
      id: 'responses',
      label: 'Feedback Responses',
      icon: <MessageSquare size={16} strokeWidth={2} aria-hidden />,
      hue: 'coral',
    },
    {
      id: 'web-monitoring',
      label: 'Web App Monitoring',
      icon: <Activity size={16} strokeWidth={2} aria-hidden />,
      hue: 'sky',
    },
    {
      id: 'android-monitoring',
      label: 'Android App Monitoring',
      icon: <Smartphone size={16} strokeWidth={2} aria-hidden />,
      hue: 'mint',
    },
  ];

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--cp-bg)' }}>
      {/* Single static header, flush at the top, never scrolls away */}
      <header
        className="sticky top-0 z-40"
        style={{
          background: 'var(--cp-surface)',
          borderBottom: '1px solid rgba(163,177,198,.25)',
        }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Top row: brand + sidebar toggle + status indicator */}
          <div className="flex items-center justify-between gap-4 h-16">
            {/* Brand */}
            <div className="flex items-center gap-3 shrink-0">
              <div className="leading-tight">
                <p className="text-lg font-bold" style={{ color: 'var(--cp-primary)' }}>
                  essential
                </p>
                <p
                  className="text-[10px] tracking-widest font-semibold whitespace-nowrap"
                  style={{ color: 'var(--cp-info)' }}
                >
                  YOUR CAMPUS ASSISTANT
                </p>
              </div>
            </div>

            <Badge tone="primary">Admin</Badge>

            {/* Right side: status indicator + sidebar toggle */}
            <div className="flex items-center gap-3 shrink-0">
              <span
                className="w-2.5 h-2.5 rounded-full"
                style={{ background: online ? 'var(--cp-success)' : 'var(--cp-danger)' }}
                title={online ? 'Backend connected' : 'Backend offline'}
                aria-label={online ? 'Backend connected' : 'Backend offline'}
              />
              {/* Sidebar Toggle Button in header */}
              <button
                type="button"
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="w-10 h-10 flex items-center justify-center transition-all duration-200"
                style={
                  sidebarOpen
                    ? {
                        borderRadius: 16,
                        background: 'var(--cp-primary)',
                        color: 'var(--cp-on-primary)',
                        boxShadow: 'var(--cp-clay)',
                      }
                    : {
                        borderRadius: 16,
                        background: 'var(--cp-surface)',
                        color: 'var(--cp-muted)',
                        boxShadow: 'var(--cp-neu-raised-sm)',
                        border: '1px solid rgba(163,177,198,.3)',
                      }
                }
                aria-label={sidebarOpen ? 'Close menu' : 'Open menu'}
                aria-expanded={sidebarOpen}
              >
                {sidebarOpen ? (
                  <X
                    size={24}
                    strokeWidth={2}
                    aria-hidden
                    className="transition-transform duration-200"
                  />
                ) : (
                  <Menu
                    size={24}
                    strokeWidth={2}
                    aria-hidden
                    className="transition-transform duration-200"
                  />
                )}
              </button>
            </div>
          </div>

          {/* Second row: Admin sub-tabs */}
          <div className="flex items-center justify-center gap-1 py-2 overflow-x-auto">
            <Tabs tabs={ADMIN_TABS} active={adminTab} onChange={setAdminTab} />
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
      <footer
        className="py-4"
        style={{
          background: 'var(--cp-surface)',
          borderTop: '1px solid rgba(163,177,198,.25)',
        }}
      >
        <div
          className="max-w-7xl mx-auto px-4 text-center text-xs"
          style={{ color: 'var(--cp-muted)' }}
        >
          essential &mdash; your campus assistant
        </div>
      </footer>
    </div>
  );
}
