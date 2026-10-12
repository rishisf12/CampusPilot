import { useEffect, useState } from 'react';
import AuthWrapper, { useAuth } from './features/auth/components/AuthWrapper';
import LiveSchedule from './features/schedule/LiveSchedule';
import VacantRoomLookup from './features/rooms/VacantRoomLookup';
import Attendance from './features/attendance/Attendance';
import ExamSeating from './features/exams/ExamSeating';
import AdminPanel from './features/admin/AdminPanel';
import Feedback from './features/feedback/Feedback';
import Teams from './features/teams/Teams';
import Profile from './features/profile/Profile';
import ErrorBanner from './shared/components/ErrorBanner';
import { SECTION_LABELS } from './shared/components/NavIcons';
import Monitoring from './features/monitoring/Monitoring';
import { healthApi } from './api';
import {
  GROUP_CLASSROOM_TABS,
  NAV_TABS,
  programmeGroupOf,
  semesterLabel,
} from './shared/constants';
import { ProfileProvider, useProfile } from './shared/hooks/useProfile';

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
  const { user } = useAuth();

  // An admin sees the developer panel instead of the student sections.
  if ((user?.role || 'student') === 'admin') {
    // Each screen owns its own hooks and state; nothing here is shared with
    // the student shell below, whose navigation is shaped by programme bundle.
    return <AdminShell />;
  }

  return (
    // Wrapped so the student shell can read the profile - the programme it
    // carries is what decides which classroom tabs exist.
    <ProfileProvider>
      <StudentShell />
    </ProfileProvider>
  );
}

function AdminShell() {
  const { user, logout, offline } = useAuth();
  const online = useBackendStatus();
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const displayName =
    user?.full_name?.trim() || user?.username || user?.email?.split('@')[0] || 'Admin';

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

/**
 * The signed-in student's app.
 *
 * The classroom tabs are not fixed: they come from the programme group the
 * student registered with. An undergraduate gets the full set; a master's or
 * doctoral student gets the shared schedule and exams, without attendance or
 * the room lookup that only answer for the undergraduate timetable.
 */
function StudentShell() {
  const { user, logout, offline } = useAuth();
  const { programme, semester } = useProfile();
  const online = useBackendStatus();
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [section, setSection] = useState<
    'classroom' | 'my-team' | 'important' | 'feedback' | 'profile'
  >('classroom');
  // Tracks whether the Classroom sub-nav is expanded. Only relevant when section === 'classroom'.
  const [classroomExpanded, setClassroomExpanded] = useState(true);
  // Tracks whether the Important sub-nav is expanded. Only relevant when section === 'important'.
  const [importantExpanded, setImportantExpanded] = useState(false);
  const [tab, setTab] = useState(() => {
    const requested = new URLSearchParams(window.location.search).get('tab');
    return NAV_TABS.some(item => item.id === requested) ? requested : 'live';
  });

  // Important sub-tabs
  const IMPORTANT_TABS = ['academics', 'placement'] as const;

  const displayName =
    user?.full_name?.trim() || user?.username || user?.email?.split('@')[0] || 'Student';

  // The bundle this student belongs to decides the classroom tabs.
  const group = programmeGroupOf(programme);
  const CLASSROOM_TABS: NavTab[] = NAV_TABS.filter(item =>
    GROUP_CLASSROOM_TABS[group].includes(item.id)
  );

  // A reload can carry a tab the bundle does not include (?tab=attendance as
  // a master's student); land on the schedule rather than a blank screen.
  const activeTab = CLASSROOM_TABS.some(item => item.id === tab) ? tab : 'live';

  // Keep the tab in the URL so a reload returns to the same view.
  const selectTab = (id: string) => {
    setTab(id);
    const url = new URL(window.location.href);
    url.searchParams.set('tab', id);
    window.history.replaceState({}, '', url);
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Single static header, flush at the top, never scrolls away */}
      <header className="sticky top-0 z-40 bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Top row: brand + user/status */}
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

            {/* User, their programme, logout and the live dot */}
            <div className="flex items-center gap-3 shrink-0">
              <span className="hidden sm:inline text-sm font-medium text-gray-700 max-w-[160px] truncate">
                {displayName}
              </span>
              {programme && (
                <span className="hidden md:inline text-xs font-semibold text-primary-600 bg-primary-50 rounded-full px-2.5 py-1 whitespace-nowrap">
                  {programme}
                  {semester ? ` · ${semesterLabel(semester)}` : ''}
                </span>
              )}
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

          {/* Second row: Main navigation (Classroom, Events, Important, Feedback, Profile) */}
          <div className="flex items-center justify-center gap-1 py-2 border-t border-gray-100 overflow-x-auto">
            <nav className="flex items-center gap-1" aria-label="Main sections">
              {(['classroom', 'my-team', 'important', 'feedback', 'profile'] as const).map(id => {
                const isActive = section === id;
                const label = SECTION_LABELS[id];
                return (
                  <button
                    key={id}
                    type="button"
                    onClick={() => {
                      if (id === 'classroom') {
                        // Toggle sub-nav when clicking Classroom tab
                        if (section === 'classroom') {
                          setClassroomExpanded(prev => !prev);
                        } else {
                          setSection('classroom');
                          setClassroomExpanded(true);
                        }
                        // When switching to classroom, reset tab to live if it is
                        // not part of this student's bundle.
                        if (activeTab !== tab) {
                          selectTab('live');
                        }
                      } else if (id === 'important') {
                        // Toggle sub-nav when clicking Important tab
                        if (section === 'important') {
                          setImportantExpanded(prev => !prev);
                        } else {
                          setSection('important');
                          setImportantExpanded(true);
                        }
                      } else {
                        setSection(id);
                        setClassroomExpanded(false);
                        setImportantExpanded(false);
                      }
                    }}
                    aria-current={isActive ? 'page' : undefined}
                    className={`px-4 py-2 text-sm font-medium whitespace-nowrap rounded-lg transition-colors ${
                      isActive
                        ? 'bg-primary-50 text-primary-600'
                        : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                    }`}
                  >
                    {label}
                  </button>
                );
              })}
            </nav>
          </div>

          {/* Third row: Classroom sub-tabs (only when Classroom is active AND expanded) */}
          {section === 'classroom' && classroomExpanded && (
            <div className="flex items-center justify-center gap-1 py-2 border-t border-gray-100 overflow-x-auto">
              <nav className="flex items-center gap-1" aria-label="Classroom">
                {CLASSROOM_TABS.map((item: NavTab) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => selectTab(item.id)}
                    aria-current={activeTab === item.id ? 'page' : undefined}
                    className={`px-3 py-1.5 text-sm font-medium whitespace-nowrap rounded-full transition-colors ${
                      activeTab === item.id
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

          {/* Fourth row: Important sub-tabs (only when Important is active AND expanded) */}
          {section === 'important' && importantExpanded && (
            <div className="flex items-center justify-center gap-1 py-2 border-t border-gray-100 overflow-x-auto">
              <nav className="flex items-center gap-1" aria-label="Important">
                {IMPORTANT_TABS.map(item => (
                  <button
                    key={item}
                    type="button"
                    onClick={() => {
                      // Could add tab state for important if needed
                    }}
                    className="px-3 py-1.5 text-sm font-medium whitespace-nowrap rounded-full transition-colors bg-white text-gray-600 border border-gray-200 hover:bg-gray-50"
                  >
                    {item === 'academics' ? 'Academics' : 'Placement Cell'}
                  </button>
                ))}
              </nav>
            </div>
          )}
        </div>
      </header>

      {/* Content, centred */}
      <main className="flex-1 w-full max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6 pt-10">
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

        {section === 'classroom' && (
          <>
            {activeTab === 'live' && <LiveSchedule onError={setConnectionError} />}
            {activeTab === 'vacant' && <VacantRoomLookup onError={setConnectionError} />}
            {activeTab === 'attendance' && <Attendance onError={setConnectionError} />}
            {activeTab === 'exam' && <ExamSeating onError={setConnectionError} />}
          </>
        )}

        {section === 'my-team' && <Teams />}

        {section === 'important' && importantExpanded && (
          <div className="text-center py-12 text-gray-500">
            <p className="text-lg font-medium">Important</p>
            <p className="mt-2">Academics and Placement Cell content coming soon.</p>
          </div>
        )}

        {section === 'feedback' && <Feedback />}

        {section === 'profile' && <Profile />}
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
