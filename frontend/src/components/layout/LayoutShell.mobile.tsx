import { Dispatch, SetStateAction } from 'react';
import { Sidebar } from '@shared/components/Sidebar';
import { HeaderTopRow } from './HeaderTopRow';
import FooterNavBar from './FooterNavBar';

interface LayoutShellProps {
  online: boolean;
  section: string;
  setSection: (id: string) => void;
  classroomExpanded: boolean;
  setClassroomExpanded: Dispatch<SetStateAction<boolean>>;
  activeTab: string;
  selectTab: (id: string) => void;
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  children: React.ReactNode;
  /** Main nav pill order; defaults to the student list. */
  navIds?: readonly string[];
  /** Classroom sub-tab order; defaults to the student list. */
  subTabIds?: readonly string[];
  /** Events sub-tab order; row shows only when expanded (Desktop+mobile). */
  eventsTabIds?: readonly string[];
  /** Whether the Events sub-row is expanded. */
  eventsExpanded?: boolean;
  activeEventTab?: string;
  selectEventTab?: (id: string) => void;
  /** Label overrides; anything not listed falls back to SECTION_LABELS. */
  labels?: Record<string, string>;
}

/** Mobile layout: header top row only; footer has sub navbar ABOVE main nav bar;
 *  right-side toggle drawer (user profile, settings, logout). */
export default function LayoutShellMobile({
  online,
  section,
  setSection,
  classroomExpanded,
  setClassroomExpanded,
  activeTab,
  selectTab,
  sidebarOpen,
  setSidebarOpen,
  children,
  navIds,
  subTabIds,
  eventsTabIds,
  eventsExpanded,
  activeEventTab,
  selectEventTab,
  labels,
}: LayoutShellProps) {
  return (
    <div
      className="min-h-screen flex flex-col overflow-x-hidden"
      style={{ background: 'var(--cp-wall)' }}
    >
      {/* Header: top row only (brand, greeting, status, theme, menu) */}
      <HeaderTopRow
        online={online}
        sidebarOpen={sidebarOpen}
        onMenu={() => setSidebarOpen(!sidebarOpen)}
      />

      {/* Main content */}
      <main className="flex-1 w-full max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 pt-16 pb-20">
        {children}
      </main>

      {/* Footer nav fixed at bottom for mobile so it never scrolls away */}
      <div
        className="fixed bottom-0 left-0 right-0 z-40"
        style={{ background: 'var(--cp-chrome)', borderTop: '1px solid rgba(255,255,255,.12)' }}
      >
        <FooterNavBar
          section={section}
          setSection={setSection}
          classroomExpanded={classroomExpanded}
          setClassroomExpanded={setClassroomExpanded}
          activeTab={activeTab}
          selectTab={selectTab}
          subNavFirst
          navIds={navIds}
          subTabIds={subTabIds}
          eventsTabIds={eventsTabIds}
          eventsExpanded={eventsExpanded}
          activeEventTab={activeEventTab}
          selectEventTab={selectEventTab}
          labels={labels}
        />
      </div>

      {/* Right-side toggle drawer: user profile, settings, logout */}
      {sidebarOpen && (
        <Sidebar
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          onSectionChange={setSection}
        />
      )}
    </div>
  );
}
