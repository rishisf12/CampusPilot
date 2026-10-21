import { lazy, useEffect, useState } from 'react';
import { CalendarDays, FileText, Menu, X } from 'lucide-react';
import { useAuth } from '@shared/auth/AuthWrapper';
import { useProfile } from '@shared/hooks/useProfile';
import { healthApi } from '@/api';
import { GROUP_CLASSROOM_TABS, NAV_TABS, programmeGroupOf } from '@shared/constants';
import { SECTION_LABELS } from '@shared/components/NavIcons';
import ErrorBanner from '@shared/components/ErrorBanner';
import { ModuleErrorBoundary } from '@shared/components/ModuleErrorBoundary';
import { Sidebar } from '@shared/components/Sidebar';
import { Tabs } from '@/components/ui';
import ThemeToggle from '@/components/layout/ThemeToggle';
import { greetingFor } from '@shared/lib/time';

/** Lazy-loaded features */
const LiveSchedule = lazy(() => import('./features/schedule/LiveSchedule'));
const ExamSeating = lazy(() => import('./features/exams/ExamSeating'));
const Feedback = lazy(() => import('./features/feedback/Feedback'));
const Profile = lazy(() => import('@shared/features/profile/Profile'));
const Settings = lazy(() => import('@shared/features/settings/Settings'));

/** Poll the backend so the header dot reflects real connectivity. */
function useBackendStatus() {
  const [online, setOnline] = useState(false);
  const [lastSync, setLastSync] = useState<number | null>(null);
  useEffect(() => {
    let cancelled = false;
    const ping = async () => {
      try {
        await healthApi.check();
        if (!cancelled) {
          setOnline(true);
          setLastSync(Date.now());
        }
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
  return { online, lastSync };
}

interface NavTab {
  id: string;
  label: string;
  icon?: React.ReactNode;
  hue?: string;
}

const TAB_META: Record<string, { icon: React.ReactNode; hue: string }> = {
  live: { icon: <CalendarDays size={16} strokeWidth={2} aria-hidden />, hue: 'indigo' },
  exam: { icon: <FileText size={16} strokeWidth={2} aria-hidden />, hue: 'amber' },
};

/**
 * Student PG Routes - defines all routes for postgraduate students.
 *
 * Classroom tabs: Live Schedule, Exam (no Attendance, no Vacant Rooms)
 * Main sections: Classroom, Events (My Team), Important, Feedback, Profile
 */
export function StudentPGRoutes() {
  const { offline } = useAuth();
  const { programme, profile } = useProfile();
  const { online, lastSync } = useBackendStatus();
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [section, setSection] = useState<
    'classroom' | 'my-team' | 'important' | 'feedback' | 'profile' | 'settings'
  >('classroom');
  // Tracks whether the Classroom sub-nav is expanded. Only relevant when section === 'classroom'.
  const [classroomExpanded, setClassroomExpanded] = useState(true);
  // Tracks whether the Important sub-nav is expanded. Only relevant when section === 'important'.
  const [importantExpanded, setImportantExpanded] = useState(false);
  // Sidebar open state
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [tab, setTab] = useState(() => {
    const requested = new URLSearchParams(window.location.search).get('tab');
    return requested && NAV_TABS.some(item => item.id === requested) ? requested : 'live';
  });

  // Important sub-tabs: the five sections the college runs under
  // "Important", in the order they are taught out.
  const IMPORTANT_TABS = [
    { id: 'academics', label: 'Academics' },
    { id: 'placement', label: 'Placement Cell' },
    { id: 'cultural', label: 'Cultural' },
    { id: 'technical', label: 'Technical' },
    { id: 'sports', label: 'Sports' },
  ] as const;
  const [importantTab, setImportantTab] = useState<string>('academics');

  // The bundle this student belongs to decides the classroom tabs.
  // PG students only get 'live' and 'exam' tabs. Chips use the short labels
  // so nothing wraps on a phone; full labels stay in NAV_TABS.
  const group = programmeGroupOf(programme);
  const CLASSROOM_TABS: NavTab[] = NAV_TABS.filter(item =>
    GROUP_CLASSROOM_TABS[group].includes(item.id)
  ).map(item => ({ ...item, label: item.short, ...(TAB_META[item.id] ?? {}) }));

  // A reload can carry a tab the bundle does not include (?tab=attendance as
  // a master's student); land on the schedule rather than a blank screen.
  const activeTab = CLASSROOM_TABS.some(item => item.id === tab) ? tab : 'live';

  const firstName = profile?.first_name?.trim();
  const todayLabel = new Date().toLocaleDateString('en-IN', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  });
  const syncTitle = !online
    ? 'Backend offline - check your connection'
    : lastSync == null
      ? 'Live - checking connection…'
      : (() => {
          const mins = Math.max(0, Math.round((Date.now() - lastSync) / 60000));
          return mins < 1 ? 'Live - synced just now' : `Live - synced ${mins} min ago`;
        })();

  // Keep the tab in the URL so a reload returns to the same view.
  const selectTab = (id: string) => {
    setTab(id);
    const url = new URL(window.location.href);
    url.searchParams.set('tab', id);
    window.history.replaceState({}, '', url);
  };

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--cp-bg)' }}>
      {/* Single static header, flush at the top, never scrolls away */}
      <header
        className="sticky top-0 z-40"
        style={{
          background: 'var(--cp-chrome)',
          borderBottom: '1px solid rgba(255,255,255,.18)',
        }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Top row: brand + greeting + status + theme + menu */}
          <div className="flex items-center justify-between gap-2 h-16">
            {/* Brand */}
            <div className="flex items-center gap-3 shrink-0">
              <div className="leading-tight">
                <p className="text-lg font-bold" style={{ color: 'var(--cp-chrome-text)' }}>
                  essential
                </p>
                <p
                  className="text-[10px] tracking-widest font-semibold whitespace-nowrap"
                  style={{ color: 'var(--cp-chrome-muted)' }}
                >
                  YOUR CAMPUS ASSISTANT
                </p>
              </div>
            </div>

            {/* Greeting: personal, truncates on narrow screens instead of wrapping */}
            <div className="flex-1 min-w-0 text-center sm:text-left px-1">
              <p
                className="text-sm font-semibold truncate"
                style={{ color: 'var(--cp-chrome-text)' }}
              >
                {greetingFor()}
                {firstName ? `, ${firstName}` : ''}
              </p>
              <p className="text-xs truncate" style={{ color: 'var(--cp-chrome-muted)' }}>
                {todayLabel}
              </p>
            </div>

            {/* Right side: status indicator + theme toggle + sidebar toggle */}
            <div className="flex items-center gap-2 shrink-0">
              <span
                className="w-2.5 h-2.5 rounded-full"
                style={{ background: online ? 'var(--cp-success)' : 'var(--cp-danger)' }}
                title={syncTitle}
                aria-label={syncTitle}
                role="status"
              />
              <ThemeToggle />
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

          {/* Second row: Main navigation (Classroom, Events, Important, Feedback) */}
          <div
            className="flex items-center justify-center gap-1 py-2 overflow-x-auto"
            style={{ borderTop: '1px solid rgba(255,255,255,.18)' }}
          >
            <nav className="flex items-center gap-1" aria-label="Main sections">
              {(['classroom', 'my-team', 'important', 'feedback'] as const).map(id => {
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
                    className="px-4 py-2 text-sm font-medium whitespace-nowrap transition-all duration-200"
                    style={
                      isActive
                        ? {
                            borderRadius: 16,
                            background: '#ffffff',
                            color: 'var(--cp-primary)',
                            boxShadow: 'var(--cp-clay)',
                          }
                        : {
                            borderRadius: 16,
                            background: 'rgba(255,255,255,.16)',
                            color: 'var(--cp-chrome-text)',
                            border: '1px solid rgba(255,255,255,.22)',
                          }
                    }
                  >
                    {label}
                  </button>
                );
              })}
            </nav>
          </div>

          {/* Third row: Classroom sub-tabs (only when Classroom is active AND expanded) */}
          {section === 'classroom' && classroomExpanded && (
            <div
              className="flex items-center justify-center gap-1 py-1 overflow-x-auto"
              style={{ borderTop: '1px solid rgba(163,177,198,.25)' }}
            >
              <Tabs tabs={CLASSROOM_TABS} active={activeTab} onChange={selectTab} onChrome />
            </div>
          )}

          {/* Fourth row: Important sub-tabs (only when Important is active AND expanded) */}
          {section === 'important' && importantExpanded && (
            <div
              className="flex items-center justify-center gap-1 py-2 overflow-x-auto"
              style={{ borderTop: '1px solid rgba(163,177,198,.25)' }}
            >
              <Tabs
                tabs={IMPORTANT_TABS.map(item => ({ id: item.id, label: item.label }))}
                active={importantTab}
                onChange={setImportantTab}
                onChrome
              />
            </div>
          )}
        </div>
      </header>

      {/* Sidebar */}
      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onSectionChange={s =>
          setSection(
            s as 'classroom' | 'my-team' | 'important' | 'feedback' | 'profile' | 'settings'
          )
        }
      />

      {/* Content, centred */}
      <main
        role="tabpanel"
        className="flex-1 w-full max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6 pt-10"
      >
        <ModuleErrorBoundary moduleName="student-pg">
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
              {activeTab === 'live' && (
                <LiveSchedule onError={setConnectionError} onJumpTab={selectTab} />
              )}
              {activeTab === 'exam' && <ExamSeating onError={setConnectionError} />}
            </>
          )}

          {section === 'my-team' && (
            <div className="text-center py-12" style={{ color: 'var(--cp-muted)' }}>
              <p className="text-lg font-medium">Collaborations</p>
              <p className="mt-2">Content coming soon.</p>
            </div>
          )}

          {section === 'important' && (
            <div className="text-center py-12" style={{ color: 'var(--cp-muted)' }}>
              <p className="text-lg font-medium">
                {IMPORTANT_TABS.find(item => item.id === importantTab)?.label ?? 'Important'}
              </p>
              <p className="mt-2">Content coming soon.</p>
            </div>
          )}

          {section === 'feedback' && <Feedback />}

          {section === 'profile' && <Profile />}

          {section === 'settings' && <Settings onOpenProfile={() => setSection('profile')} />}
        </ModuleErrorBoundary>
      </main>

      {/* Single footer */}
      <footer
        className="py-4"
        style={{
          background: 'var(--cp-chrome)',
          borderTop: '1px solid rgba(255,255,255,.18)',
        }}
      >
        <div
          className="max-w-7xl mx-auto px-4 text-center text-xs"
          style={{ color: 'var(--cp-chrome-muted)' }}
        >
          essential &mdash; your campus assistant
        </div>
      </footer>
    </div>
  );
}
