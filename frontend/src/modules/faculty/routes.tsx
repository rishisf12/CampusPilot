/**
 * Faculty Routes — student-mirrored layout with lazy-classroom sub-tabs.
 *
 * Main nav: Classroom | Important | Feedback | Profile (no attendance/task —
 * those are student features). Classroom sub-tabs: Live Schedule | Vacant
 * Rooms. Live Schedule is filtered by the account's timetable notation, so it
 * shows every cohort the instructor teaches across all branches and semesters.
 */
import { lazy, useEffect, useState, useCallback } from 'react';
import { useAuth } from '@shared/auth/AuthWrapper';
import { healthApi } from '@/api';
import ErrorBanner from '@shared/components/ErrorBanner';
import { ModuleErrorBoundary } from '@shared/components/ModuleErrorBoundary';
import LayoutShellMobile from '@/components/layout/LayoutShell.mobile';
import LayoutShellDesktop from '@/components/layout/LayoutShell.desktop';

/** Lazy-loaded features */
const FacultyLiveSchedule = lazy(() => import('./features/schedule/FacultyLiveSchedule'));
const VacantRoomLookup = lazy(() => import('@shared/features/rooms/VacantRoomLookup'));
const Feedback = lazy(() => import('@shared/features/feedback/Feedback'));
const FacultyProfile = lazy(() => import('./features/profile/FacultyProfile'));
const Events = lazy(() => import('@shared/features/events/Events'));

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
    return () => {
      window.removeEventListener('resize', onResize);
      setIsMobile(window.innerWidth < 768);
    };
  }, []);
  return isMobile;
}

type SectionId = 'classroom' | 'important' | 'feedback' | 'profile';

/** Faculty main nav: no attendance/task pills — those belong to students. */
const FACULTY_NAV = [
  { id: 'classroom', label: 'Classroom' },
  { id: 'important', label: 'Events' },
  { id: 'feedback', label: 'Feedback' },
  { id: 'profile', label: 'Profile' },
] as const;

/** Faculty classroom sub-tabs: live schedule + vacant rooms. */
const FACULTY_SUB_TABS = [
  { id: 'live', label: 'Live Schedule' },
  { id: 'vacant', label: 'Vacant Rooms' },
] as const;

const FACULTY_LABELS: Record<string, string> = {
  classroom: 'Classroom',
  important: 'Events',
  feedback: 'Feedback',
  profile: 'Profile',
  live: 'Live Schedule',
  vacant: 'Vacant Rooms',
};

export function FacultyRoutes() {
  const { offline } = useAuth();
  const { online } = useBackendStatus();
  const isMobile = useIsMobile();
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [section, setSection] = useState<SectionId>('classroom');
  // Tracks whether the Classroom sub-nav is expanded. Only relevant when section === 'classroom'.
  const [classroomExpanded, setClassroomExpanded] = useState(true);
  // Events sub-row mirrors the Classroom mechanism: expands with the section
  // and toggles when the Events pill is clicked again.
  const [eventsExpanded, setEventsExpanded] = useState(false);
  const [eventTab, setEventTab] = useState('jagrati');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [tab, setTab] = useState(() => {
    const requested = new URLSearchParams(window.location.search).get('tab');
    return requested && FACULTY_SUB_TABS.some(item => item.id === requested) ? requested : 'live';
  });

  // A reload can carry a tab the bundle does not include; land on the schedule.
  const activeTab = FACULTY_SUB_TABS.some(item => item.id === tab) ? tab : 'live';

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
      } else if (id === 'vacant') {
        setSection('classroom');
        setClassroomExpanded(true);
        selectTab('vacant');
      } else if (id === 'live') {
        setSection('classroom');
        setClassroomExpanded(true);
        selectTab('live');
      } else if (id === 'important') {
        if (section === 'important') {
          setEventsExpanded(prev => !prev);
        } else {
          setSection('important');
          setEventsExpanded(true);
        }
        setClassroomExpanded(false);
      } else if (id === 'feedback') {
        setSection('feedback');
        setClassroomExpanded(false);
      } else if (id === 'profile') {
        setSection('profile');
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
    collapsed,
    setCollapsed: handleToggleCollapse,
    navIds: FACULTY_NAV.map(item => item.id),
    subTabIds: FACULTY_SUB_TABS.map(item => item.id),
    eventsTabIds: ['jagrati', 'cultural', 'technical', 'sports'],
    eventsExpanded,
    activeEventTab: eventTab,
    selectEventTab: setEventTab,
    labels: FACULTY_LABELS,
  };

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--cp-wall)' }}>
      {isMobile ? (
        <LayoutShellMobile {...layoutProps}>
          <ModuleErrorBoundary moduleName="faculty">{renderContent()}</ModuleErrorBoundary>
        </LayoutShellMobile>
      ) : (
        <LayoutShellDesktop {...layoutProps}>
          <ModuleErrorBoundary moduleName="faculty">{renderContent()}</ModuleErrorBoundary>
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
            {activeTab === 'live' && <FacultyLiveSchedule onError={setConnectionError} />}
            {activeTab === 'vacant' && <VacantRoomLookup onError={setConnectionError} />}
          </>
        )}

        {section === 'important' && <Events tab={eventTab} />}

        {section === 'feedback' && <Feedback />}

        {section === 'profile' && <FacultyProfile />}
      </>
    );
  }
}
