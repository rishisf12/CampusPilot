import { Dispatch, SetStateAction } from 'react';
import { Sidebar } from '@shared/components/Sidebar';
import { SECTION_ICONS, SECTION_LABELS } from '@shared/components/NavIcons';
import { CheckCircle2, DoorOpen, FileText, CalendarDays } from 'lucide-react';

/** Sub-tab icons (live / attendance / vacant / exam), matching the quick-action cards. */
const SUB_TAB_ICONS: Record<string, (props: { className?: string }) => React.ReactNode> = {
  live: ({ className }) => <CalendarDays className={className} strokeWidth={2} aria-hidden />,
  attendance: ({ className }) => <CheckCircle2 className={className} strokeWidth={2} aria-hidden />,
  vacant: ({ className }) => <DoorOpen className={className} strokeWidth={2} aria-hidden />,
  exam: ({ className }) => <FileText className={className} strokeWidth={2} aria-hidden />,
};
import { HeaderTopRow } from './HeaderTopRow';

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
  /** Events sub-tab order (Jagrati/Cultural/Technical/Sports); omits the row. */
  eventsTabIds?: readonly string[];
  /** Whether the Events sub-row is expanded, mirroring classroomExpanded. */
  eventsExpanded?: boolean;
  /** The event stream the shell should mark active. */
  activeEventTab?: string;
  selectEventTab?: (id: string) => void;
  /** Label overrides; anything not listed falls back to SECTION_LABELS. */
  labels?: Record<string, string>;
}

/** Desktop layout: header top row + main nav + classroom sub-tabs in header,
 *  no footer nav (footer is simple text). No left sidebar.
 *  Right-side toggle drawer (user profile, settings, logout). */
export default function LayoutShellDesktop({
  online,
  section,
  setSection,
  classroomExpanded,
  activeTab,
  selectTab,
  sidebarOpen,
  setSidebarOpen,
  children,
  navIds = ['classroom', 'my-team', 'important', 'feedback', 'task'],
  subTabIds = ['live', 'attendance', 'vacant', 'exam'],
  eventsTabIds,
  eventsExpanded = false,
  activeEventTab,
  selectEventTab,
  labels,
}: LayoutShellProps) {
  /** One pill row of sub-tabs, styled identically for Classroom and Events. */
  const renderSubRow = (
    ids: readonly string[],
    active: string | undefined,
    onSelect?: (id: string) => void
  ) => (
    <div className="flex justify-center">
      <nav
        className="flex gap-2 overflow-x-auto w-full max-w-xl px-2 pb-1.5"
        aria-label="Sub navigation"
      >
        {ids.map(id => {
          const isActive = id === active;
          const SubIcon = SUB_TAB_ICONS[id];
          return (
            <button
              key={id}
              type="button"
              onClick={() => onSelect?.(id)}
              aria-current={isActive ? 'page' : undefined}
              className="inline-flex items-center justify-center gap-2 px-3 py-1.5 text-sm font-medium whitespace-nowrap flex-1 min-w-max rounded-lg transition-all duration-200"
              style={
                isActive
                  ? {
                      borderRadius: '0.5rem',
                      background: 'var(--cp-surface)',
                      color: 'var(--cp-primary)',
                      boxShadow: 'var(--cp-clay)',
                      border: '1px solid rgba(255,255,255,.22)',
                    }
                  : {
                      borderRadius: '0.5rem',
                      background: 'rgba(255,255,255,.06)',
                      color: 'var(--cp-text)',
                      border: '1px solid rgba(163,177,198,.3)',
                    }
              }
            >
              {SubIcon && <SubIcon className="w-4 h-4" />}
              {labels?.[id] ?? SECTION_LABELS[id] ?? id}
            </button>
          );
        })}
      </nav>
    </div>
  );

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--cp-wall)' }}>
      {/* Header flush to the top and side edges; navs attach below it. Desktop
          only — mobile keeps its own shell (LayoutShell.mobile). */}
      <HeaderTopRow
        online={online}
        sidebarOpen={sidebarOpen}
        onMenu={() => setSidebarOpen(!sidebarOpen)}
      />

      {/* Main navigation bar — attached to the header, centred, compact width */}
      <div className="flex justify-center">
        <nav
          className="flex gap-2 overflow-x-auto w-full max-w-2xl pt-1.5 pb-1.5 px-2"
          aria-label="Main sections"
        >
          {navIds.map(id => {
            const isActive = section === id;
            const label = labels?.[id] ?? SECTION_LABELS[id];
            const Icon = SECTION_ICONS[id];
            return (
              <button
                key={id}
                type="button"
                onClick={() => setSection(id)}
                aria-current={isActive ? 'page' : undefined}
                className="inline-flex items-center justify-center gap-2 px-3 py-1.5 text-sm font-medium whitespace-nowrap flex-1 min-w-max rounded-lg transition-all duration-200"
                style={
                  isActive
                    ? {
                        borderRadius: '0.5rem',
                        background: 'var(--cp-surface)',
                        color: 'var(--cp-primary)',
                        boxShadow: 'var(--cp-clay)',
                        border: '1px solid rgba(255,255,255,.22)',
                      }
                    : {
                        borderRadius: '0.5rem',
                        background: 'rgba(255,255,255,.06)',
                        color: 'var(--cp-text)',
                        border: '1px solid rgba(163,177,198,.3)',
                      }
                }
              >
                <Icon className="w-4 h-4" />
                {label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Sub-tabs — attached to the main nav, centred, narrower. Classroom has
          its own row; Events shows its streams the same way, toggled by the
          Events pill itself. */}
      {section === 'classroom' &&
        classroomExpanded &&
        renderSubRow(subTabIds, activeTab, selectTab)}
      {section === 'important' &&
        eventsExpanded &&
        eventsTabIds &&
        eventsTabIds.length > 0 &&
        renderSubRow(eventsTabIds, activeEventTab, selectEventTab)}

      {/* Main content: keeps side padding even though the header is full-bleed */}
      <main className="flex-1 min-w-0 px-3 pt-2 pb-20">{children}</main>

      {/* Footer: simple text only (desktop) — nav stays in header */}
      <footer className="py-4 px-3 text-center text-xs" style={{ color: 'var(--cp-muted)' }}>
        essential &mdash; your campus assistant
      </footer>

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
