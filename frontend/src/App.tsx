import { useEffect, useState } from 'react';
import AuthWrapper, { useAuth } from './components/AuthWrapper';
import LiveSchedule from './features/classroom/LiveSchedule';
import VacantRoomLookup from './features/classroom/VacantRoomLookup';
import Attendance from './features/classroom/Attendance';
import ExamSeating from './features/classroom/ExamSeating';
import AdminPanel from './features/admin/AdminPanel';
import Feedback from './features/feedback/Feedback';
import Teams from './features/myteam/Teams';
import Profile from './features/profile/Profile';
import ErrorBanner from './components/ErrorBanner';
import { SECTION_ICONS, SECTION_LABELS } from './components/NavIcons';
import Monitoring from './features/monitoring/Monitoring';
import { healthApi } from './api';
import { NAV_TABS } from './constants';
import { ProfileProvider } from './hooks/useProfile';

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

interface NavTab {
  id: string;
  label: string;
}

function Shell() {
  const { user, logout, offline } = useAuth();
  const [section, setSection] = useState<'classroom' | 'my-team' | 'feedback' | 'profile'>(
    'classroom'
  );
  const [tab, setTab] = useState(() => {
    const requested = new URLSearchParams(window.location.search).get('tab');
    return NAV_TABS.some(item => item.id === requested) ? requested : 'live';
  });
  const online = useBackendStatus();
  const [connectionError, setConnectionError] = useState<string | null>(null);

  // Admin sub-tabs. The default is deliberately the existing Feedback Responses
  // panel, so nothing about current admin behaviour changes; monitoring is
  // added alongside it rather than replacing it.
  const ADMIN_TABS: AdminTab[] = [
    { id: 'responses', label: 'Feedback Responses' },
    { id: 'web-monitoring', label: 'Web App Monitoring' },
    { id: 'android-monitoring', label: 'Android App Monitoring' },
    { id: 'profile', label: 'Profile' },
  ];
  const [adminTab, setAdminTab] = useState('responses');

  // Keep the tab in the URL so a reload returns to the same view.
  const selectTab = (id: string) => {
    setTab(id);
    const url = new URL(window.location.href);
    url.searchParams.set('tab', id);
    window.history.replaceState({}, '', url);
  };

  const displayName =
    user?.full_name?.trim() || user?.username || user?.email?.split('@')[0] || 'Student';

  // Classroom sub-tabs
  const CLASSROOM_TABS = NAV_TABS;

  // An admin sees the developer panel instead of the student sections.
  if ((user?.role || 'student') === 'admin') {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col">
        <header className="sticky top-0 z-40 bg-white border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between gap-4 h-16">
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

              <div className="flex items-center gap-3 shrink-0">
                <span className="hidden sm:inline text-sm font-medium text-gray-700 max-w-[160px] truncate">
                  {displayName}
                </span>
                <button type="button" onClick={logout} className="btn-ghost">
                  Logout
                </button>
                <span
                  className={`w-2.5 h-2.5 rounded-full ${online ? 'bg-success-500' : 'bg-danger-500'}`}
                  title={online ? 'Backend connected' : 'Backend offline'}
                  aria-label={online ? 'Backend connected' : 'Backend offline'}
                />
              </div>
            </div>
          </div>
        </header>

        <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {offline && !online && (
            <ErrorBanner
              message="Backend offline - start it with: uvicorn main:app --port 8001"
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

          {/* Admin sub-tabs */}
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

          <ProfileProvider>
            {adminTab === 'responses' && <AdminPanel onError={setConnectionError} />}
            {adminTab === 'web-monitoring' && <Monitoring platformGroup="Web App Monitoring" />}
            {adminTab === 'android-monitoring' && (
              <Monitoring platformGroup="Android App Monitoring" />
            )}
            {adminTab === 'profile' && <Profile />}
          </ProfileProvider>
        </main>

        <footer className="bg-white border-t border-gray-200 py-4">
          <div className="max-w-7xl mx-auto px-4 text-center text-xs text-gray-500">
            essential &mdash; your campus assistant
          </div>
        </footer>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Single static header, flush at the top, never scrolls away */}
      <header className="sticky top-0 z-40 bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Top row: brand + main nav (Classroom, My Team, Feedback) + user/status */}
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

            {/* Main navigation: Classroom | My Team | Feedback | Profile.
                Each glyph is a self-contained silhouette, but the caption under
                it means nobody has to guess on first use. `aria-label` repeats
                the name for screen readers, since the caption is a sibling. */}
            <nav className="flex items-center gap-2 shrink-0" aria-label="Main sections">
              {(['classroom', 'my-team', 'feedback', 'profile'] as const).map(id => {
                const isActive = section === id;
                const Icon = SECTION_ICONS[id];
                const label = SECTION_LABELS[id];
                return (
                  <button
                    key={id}
                    type="button"
                    onClick={() => {
                      setSection(id);
                      // When switching to classroom, reset tab to live if not already a classroom tab
                      if (id === 'classroom' && !CLASSROOM_TABS.some(t => t.id === tab)) {
                        selectTab('live');
                      }
                    }}
                    aria-current={isActive ? 'page' : undefined}
                    aria-label={label}
                    className={`flex flex-col items-center gap-1 px-3 py-2 rounded-xl transition-colors ${
                      isActive
                        ? 'bg-primary-50 text-primary-600'
                        : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                    }`}
                  >
                    <Icon />
                    <span
                      className={`text-[11px] leading-none whitespace-nowrap ${
                        isActive ? 'font-semibold' : 'font-medium'
                      }`}
                    >
                      {label}
                    </span>
                  </button>
                );
              })}
            </nav>

            {/* User, logout and the live dot */}
            <div className="flex items-center gap-3 shrink-0">
              <span className="hidden sm:inline text-sm font-medium text-gray-700 max-w-[160px] truncate">
                {displayName}
              </span>
              <button type="button" onClick={logout} className="btn-ghost">
                Logout
              </button>
              <span
                className={`w-2.5 h-2.5 rounded-full ${online ? 'bg-success-500' : 'bg-danger-500'}`}
                title={online ? 'Backend connected' : 'Backend offline'}
                aria-label={online ? 'Backend connected' : 'Backend offline'}
              />
            </div>
          </div>

          {/* Second row: Classroom sub-tabs (only when Classroom is active) */}
          {section === 'classroom' && (
            <div className="flex items-center justify-center gap-1 py-2 border-t border-gray-100 overflow-x-auto">
              <nav className="flex items-center gap-1" aria-label="Classroom">
                {CLASSROOM_TABS.map((item: NavTab) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => selectTab(item.id)}
                    aria-current={tab === item.id ? 'page' : undefined}
                    className={`px-3 py-1.5 text-sm font-medium whitespace-nowrap rounded-full transition-colors ${
                      tab === item.id
                        ? 'bg-primary-500 text-white'
                        : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </nav>
            </div>
          )}
        </div>
      </header>

      {/* Content, centred */}
      <main className="flex-1 w-full max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {offline && !online && (
          <ErrorBanner
            message="Backend offline - start it with: uvicorn main:app --port 8001"
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

        <ProfileProvider>
          {section === 'classroom' && (
            <>
              {tab === 'live' && <LiveSchedule onError={setConnectionError} />}
              {tab === 'vacant' && <VacantRoomLookup onError={setConnectionError} />}
              {tab === 'attendance' && <Attendance onError={setConnectionError} />}
              {tab === 'exam' && <ExamSeating onError={setConnectionError} />}
            </>
          )}

          {section === 'my-team' && <Teams />}

          {section === 'feedback' && <Feedback />}

          {section === 'profile' && <Profile />}
        </ProfileProvider>
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

export default function App() {
  return (
    <AuthWrapper>
      <Shell />
    </AuthWrapper>
  );
}
