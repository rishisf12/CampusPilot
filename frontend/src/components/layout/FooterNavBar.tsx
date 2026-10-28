import { Dispatch, SetStateAction } from 'react';
import { SECTION_ICONS, SECTION_LABELS } from '@shared/components/NavIcons';
import { CheckCircle2, DoorOpen, FileText, CalendarDays } from 'lucide-react';

/** Sub-tab icons (live / attendance / vacant / exam), matching the quick-action cards. */
const SUB_TAB_ICONS: Record<string, (props: { className?: string }) => React.ReactNode> = {
  live: ({ className }) => <CalendarDays className={className} strokeWidth={2} aria-hidden />,
  attendance: ({ className }) => <CheckCircle2 className={className} strokeWidth={2} aria-hidden />,
  vacant: ({ className }) => <DoorOpen className={className} strokeWidth={2} aria-hidden />,
  exam: ({ className }) => <FileText className={className} strokeWidth={2} aria-hidden />,
};

interface FooterNavBarProps {
  section: string;
  setSection: (id: string) => void;
  classroomExpanded: boolean;
  setClassroomExpanded: Dispatch<SetStateAction<boolean>>;
  activeTab: string;
  selectTab: (id: string) => void;
  /** When true, sub navbar renders above the main navigation bar (mobile only). */
  subNavFirst?: boolean;
}

export default function FooterNavBar({
  section,
  setSection,
  classroomExpanded,
  activeTab,
  selectTab,
  subNavFirst = false,
}: FooterNavBarProps) {
  const handleSectionClick = (id: string) => {
    setSection(id);
  };

  const renderMainNav = () => (
    <div
      className="py-1"
      style={{
        borderBottom: '1px solid rgba(163,177,198,.3)',
        marginBottom: '-1px',
        paddingBottom: '2px',
      }}
    >
      <nav className="flex gap-2 overflow-x-auto" aria-label="Main sections">
        {(['classroom', 'my-team', 'important', 'feedback', 'task'] as const).map(id => {
          const isActive = section === id;
          const label = SECTION_LABELS[id];
          const Icon = SECTION_ICONS[id];
          return (
            <button
              key={id}
              type="button"
              onClick={() => handleSectionClick(id)}
              aria-current={isActive ? 'page' : undefined}
              className="inline-flex items-center justify-center gap-2 px-3 py-1.5 text-[10px] sm:text-sm font-medium whitespace-nowrap flex-1 min-w-0 md:min-w-max rounded-lg transition-all duration-200"
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
              <Icon className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              {label}
            </button>
          );
        })}
      </nav>
    </div>
  );

  const renderSubNav = () => (
    <div
      className="py-2"
      style={{ borderTop: '1px solid rgba(163,177,198,.3)', marginTop: '2px', paddingTop: '2px' }}
    >
      <nav className="flex gap-2 overflow-x-auto" aria-label="Classroom sub-tabs">
        {(['live', 'attendance', 'vacant', 'exam'] as const).map(id => {
          const isActive = id === activeTab;
          const SubIcon = SUB_TAB_ICONS[id];
          return (
            <button
              key={id}
              type="button"
              onClick={() => selectTab(id)}
              aria-current={isActive ? 'page' : undefined}
              className="inline-flex items-center justify-center gap-2 px-3 py-1.5 text-[10px] sm:text-sm font-medium whitespace-nowrap flex-1 min-w-0 md:min-w-max rounded-lg transition-all duration-200"
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
              {SubIcon && <SubIcon className="w-3.5 h-3.5 sm:w-4 sm:h-4" />}
              {SECTION_LABELS[id] ?? id}
            </button>
          );
        })}
      </nav>
    </div>
  );

  return (
    <footer
      className="py-3"
      style={{
        background: 'var(--cp-chrome)',
        borderTop: '1px solid rgba(163,177,198,.3)',
        marginTop: '2px',
        paddingTop: '2px',
      }}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {subNavFirst ? (
          <>
            {/* Sub navbar on top (mobile) */}
            {section === 'classroom' && classroomExpanded && renderSubNav()}
            {/* Main navigation bar below */}
            {renderMainNav()}
          </>
        ) : (
          <>
            {/* Main navigation bar on top */}
            {renderMainNav()}
            {/* Sub navbar below */}
            {section === 'classroom' && classroomExpanded && renderSubNav()}
          </>
        )}
      </div>
    </footer>
  );
}
