import { lazy, useEffect, useState } from 'react';
import { useAuth } from '@shared/auth/AuthWrapper';
import { useProfile } from '@shared/hooks/useProfile';
import { healthApi } from '@/api';
import { GROUP_CLASSROOM_TABS, NAV_TABS, programmeGroupOf } from '@shared/constants';
import { SECTION_LABELS, SECTION_ICONS } from '@shared/components/NavIcons';
import ErrorBanner from '@shared/components/ErrorBanner';
import { ModuleErrorBoundary } from '@shared/components/ModuleErrorBoundary';
import { Sidebar } from '@shared/components/Sidebar';

/** Lazy-loaded features */
const LiveSchedule = lazy(() => import('./features/schedule/LiveSchedule'));
const Attendance = lazy(() => import('./features/attendance/Attendance'));
const VacantRoomLookup = lazy(() => import('./features/rooms/VacantRoomLookup'));
const ExamSeating = lazy(() => import('./features/exams/ExamSeating'));
const Teams = lazy(() => import('./features/teams/Teams'));
const Feedback = lazy(() => import('./features/feedback/Feedback'));
const Profile = lazy(() => import('@shared/features/profile/Profile'));

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

/** Simple icon for Important section */
function ImportantIcon({ className = 'w-5 h-5' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
    </svg>
  );
}

const SECTION_ICON_COMPONENTS = {
  classroom: SECTION_ICONS.classroom,
  'my-team': SECTION_ICONS['my-team'],
  feedback: SECTION_ICONS.feedback,
  profile: SECTION_ICONS.profile,
  important: ImportantIcon,
};

interface NavTab {
  id: string;
  label: string;
}

/**
 * Student UG Routes - defines all routes for undergraduate students.
 *
 * Classroom tabs: Live Schedule, Attendance, Vacant Rooms, Exam
 * Main sections: Classroom, Events (My Team), Important, Feedback, Profile
 */
export function StudentUGRoutes() {
  const { offline } = useAuth();
  const { programme } = useProfile();
  const online = useBackendStatus();
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [section, setSection] = useState<
    'classroom' | 'my-team' | 'important' | 'feedback' | 'profile'
  >('classroom');
  // Tracks whether the Classroom sub-nav is expanded. Only relevant when section === 'classroom'.
  const [classroomExpanded, setClassroomExpanded] = useState(true);
  // Tracks whether the Important sub-nav is expanded. Only relevant when section === 'important'.
  const [importantExpanded, setImportantExpanded] = useState(false);
  // Sidebar open state
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [tab, setTab] = useState(() => {
    const requested = new URLSearchParams(window.location.search).get('tab');
    return NAV_TABS.some(item => item.id === requested) ? requested : 'live';
  });

  // Important sub-tabs
  const IMPORTANT_TABS = ['academics', 'placement'] as const;

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

          {/* Second row: Main navigation (Classroom, Events, Important, Feedback) */}
          <div className="flex items-center justify-center gap-1 py-2 border-t border-gray-100 overflow-x-auto">
            <nav className="flex items-center gap-1" aria-label="Main sections">
              {(['classroom', 'my-team', 'important', 'feedback'] as const).map(id => {
                const isActive = section === id;
                const label = SECTION_LABELS[id];
                const Icon = SECTION_ICON_COMPONENTS[id];
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
                    className={`px-4 py-2 text-sm font-medium whitespace-nowrap rounded-lg transition-colors flex items-center gap-1.5 ${
                      isActive
                        ? 'bg-primary-50 text-primary-600'
                        : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                    }`}
                  >
                    <Icon className="w-5 h-5" />
                    <span className="hidden sm:inline">{label}</span>
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

      {/* Sidebar */}
      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onSectionChange={s =>
          setSection(s as 'classroom' | 'my-team' | 'important' | 'feedback' | 'profile')
        }
      />

      {/* Content, centred */}
      <main className="flex-1 w-full max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6 pt-10">
        <ModuleErrorBoundary moduleName="student-ug">
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

          {section === 'important' && (
            <div className="text-center py-12 text-gray-500">
              <p className="text-lg font-medium">Important</p>
              <p className="mt-2">Academics and Placement Cell content coming soon.</p>
            </div>
          )}

          {section === 'feedback' && <Feedback />}

          {section === 'profile' && <Profile />}
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
