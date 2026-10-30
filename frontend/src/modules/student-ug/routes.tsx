import { lazy, useEffect, useState, useCallback } from 'react';
import { CalendarDays, CheckCircle2, DoorOpen, FileText } from 'lucide-react';
import { useAuth } from '@shared/auth/AuthWrapper';
import { useProfile } from '@shared/hooks/useProfile';
import { healthApi } from '@/api';
import { GROUP_CLASSROOM_TABS, NAV_TABS, programmeGroupOf } from '@shared/constants';
import ErrorBanner from '@shared/components/ErrorBanner';
import { ModuleErrorBoundary } from '@shared/components/ModuleErrorBoundary';
import LayoutShellMobile from '@/components/layout/LayoutShell.mobile';
import LayoutShellDesktop from '@/components/layout/LayoutShell.desktop';
const Events = lazy(() => import('@shared/features/events/Events'));

/** Lazy-loaded features */
const LiveSchedule = lazy(() => import('./features/schedule/LiveSchedule'));
const Attendance = lazy(() => import('./features/attendance/Attendance'));
const VacantRoomLookup = lazy(() => import('./features/rooms/VacantRoomLookup'));
const ExamSeating = lazy(() => import('./features/exams/ExamSeating'));
const Feedback = lazy(() => import('./features/feedback/Feedback'));
const TaskTracker = lazy(() => import('@shared/features/task/TaskTracker'));
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

/** Detect mobile viewport for separate mobile/desktop layout shells. */
function useIsMobile() {
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  return isMobile;
}

type SectionId =
  'classroom' | 'my-team' | 'important' | 'feedback' | 'task' | 'profile' | 'settings';

interface NavTab {
  id: string;
  label: string;
  icon?: React.ReactNode;
  hue?: string;
}

const TAB_META: Record<string, { icon: React.ReactNode; hue: string }> = {
  live: { icon: <CalendarDays size={16} strokeWidth={2} aria-hidden />, hue: 'indigo' },
  attendance: { icon: <CheckCircle2 size={16} strokeWidth={2} aria-hidden />, hue: 'mint' },
  vacant: { icon: <DoorOpen size={16} strokeWidth={2} aria-hidden />, hue: 'sky' },
  exam: { icon: <FileText size={16} strokeWidth={2} aria-hidden />, hue: 'amber' },
};

/**
 * Student UG Routes - defines all routes for undergraduate students.
 *
 * Layout: header top row + classroom sub-tabs (3rd sub navbar) in header;
 * main navigation bar + sub navbar in footer.
 *
 * Classroom tabs: Live Schedule, Attendance, Vacant Rooms, Exam
 * Main sections: Classroom, Events (My Team), Important, Feedback, Profile
 */
export function StudentUGRoutes() {
  const { offline } = useAuth();
  const { programme } = useProfile();
  const { online } = useBackendStatus();
  const isMobile = useIsMobile();
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [section, setSection] = useState<SectionId>('classroom');
  // Tracks whether the Classroom sub-nav is expanded. Only relevant when section === 'classroom'.
  const [classroomExpanded, setClassroomExpanded] = useState(true);
  // Events sub-row mirrors the Classroom mechanism: expands with the section and
  // toggles when the Events pill is clicked again.
  const [eventsExpanded, setEventsExpanded] = useState(false);
  const [eventTab, setEventTab] = useState('jagrati');
  // Sidebar open state (mobile drawer / desktop collapsed)
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [tab, setTab] = useState(() => {
    const requested = new URLSearchParams(window.location.search).get('tab');
    return requested && NAV_TABS.some(item => item.id === requested) ? requested : 'live';
  });

  // The bundle this student belongs to decides the classroom tabs.
  const group = programmeGroupOf(programme);
  const CLASSROOM_TABS: NavTab[] = NAV_TABS.filter(item =>
    GROUP_CLASSROOM_TABS[group].includes(item.id)
  ).map(item => ({ ...item, label: item.short, ...(TAB_META[item.id] ?? {}) }));

  // A reload can carry a tab the bundle does not include; land on the schedule.
  const activeTab = CLASSROOM_TABS.some(item => item.id === tab) ? tab : 'live';

  // Keep the tab in the URL so a reload returns to the same view.
  const selectTab = useCallback((id: string) => {
    setTab(id);
    const url = new URL(window.location.href);
    url.searchParams.set('tab', id);
    window.history.replaceState({}, '', url);
  }, []);

  // Memoized callback refs so layout shell children don't re-render unnecessarily
  const handleSectionChange = useCallback(
    (id: string) => {
      // Map CATEGORY_NAV sidebar IDs to app sections/tabs
      if (id === 'classroom') {
        if (section === 'classroom') {
          setClassroomExpanded(prev => !prev);
        } else {
          setSection('classroom');
          setClassroomExpanded(true);
        }
        if (activeTab !== tab) {
          selectTab('live');
        }
      } else if (id === 'attendance') {
        setSection('classroom');
        setClassroomExpanded(true);
        selectTab('attendance');
      } else if (id === 'vacant') {
        setSection('classroom');
        setClassroomExpanded(true);
        selectTab('vacant');
      } else if (id === 'exam') {
        setSection('classroom');
        setClassroomExpanded(true);
        selectTab('exam');
      } else if (id === 'important') {
        if (section === 'important') {
          setEventsExpanded(prev => !prev);
        } else {
          setSection('important');
          setEventsExpanded(true);
        }
        setClassroomExpanded(false);
      } else if (id === 'my-team') {
        setSection('my-team');
        setClassroomExpanded(false);
      } else if (id === 'feedback') {
        setSection('feedback');
        setClassroomExpanded(false);
      } else if (id === 'task') {
        setSection('task');
        setClassroomExpanded(false);
      } else if (id === 'profile') {
        setSection('profile');
        setClassroomExpanded(false);
      } else if (id === 'settings') {
        setSection('settings');
        setClassroomExpanded(false);
      } else {
        // Unknown ID: fall back to classroom
        setSection('classroom');
        setClassroomExpanded(true);
        selectTab('live');
      }
    },
    [section, tab, activeTab, selectTab]
  );

  const handleToggleSidebar = useCallback(() => {
    setSidebarOpen(prev => !prev);
  }, []);

  const handleToggleCollapse = useCallback(() => {
    setCollapsed(prev => !prev);
  }, []);

  const layoutProps = {
    online,
    section,
    setSection: handleSectionChange,
    classroomExpanded,
    setClassroomExpanded,
    activeTab,
    selectTab,
    sidebarOpen,
    setSidebarOpen: handleToggleSidebar,
    eventsTabIds: ['jagrati', 'cultural', 'technical', 'sports'],
    eventsExpanded,
    activeEventTab: eventTab,
    selectEventTab: setEventTab,
    collapsed,
    setCollapsed: handleToggleCollapse,
  };

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--cp-wall)' }}>
      {isMobile ? (
        <LayoutShellMobile {...layoutProps}>
          <ModuleErrorBoundary moduleName="student-ug">{renderContent()}</ModuleErrorBoundary>
        </LayoutShellMobile>
      ) : (
        <LayoutShellDesktop {...layoutProps}>
          <ModuleErrorBoundary moduleName="student-ug">{renderContent()}</ModuleErrorBoundary>
        </LayoutShellDesktop>
      )}
    </div>
  );

  function renderContent() {
    return (
      <>
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

        {section === 'my-team' && (
          <div className="text-center py-12" style={{ color: 'var(--cp-muted)' }}>
            <p className="text-lg font-medium">Collaborations</p>
            <p className="mt-2">Content coming soon.</p>
          </div>
        )}

        {section === 'important' && <Events tab={eventTab} />}

        {section === 'feedback' && <Feedback />}

        {section === 'task' && <TaskTracker />}

        {section === 'profile' && <Profile />}

        {section === 'settings' && <Settings onOpenProfile={() => setSection('profile')} />}
      </>
    );
  }
}
