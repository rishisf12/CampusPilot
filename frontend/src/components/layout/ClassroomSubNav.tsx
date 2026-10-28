import { GROUP_CLASSROOM_TABS, NAV_TABS, programmeGroupOf } from '@shared/constants';
import { useProfile } from '@shared/hooks/useProfile';

interface ClassroomSubNavProps {
  section: string;
  classroomExpanded: boolean;
  activeTab: string;
  selectTab: (id: string) => void;
}

export function ClassroomSubNav({
  section,
  classroomExpanded,
  activeTab,
  selectTab,
}: ClassroomSubNavProps) {
  const { programme } = useProfile();

  // Only render when classroom section is active AND expanded
  if (section !== 'classroom' || !classroomExpanded) {
    return null;
  }

  const group = programmeGroupOf(programme);
  const CLASSROOM_TABS = NAV_TABS.filter(item => GROUP_CLASSROOM_TABS[group].includes(item.id));

  const activeTabId = CLASSROOM_TABS.some(item => item.id === activeTab)
    ? activeTab
    : (CLASSROOM_TABS[0]?.id ?? 'live');

  return (
    <div
      className="flex items-center justify-center gap-1 overflow-x-auto"
      style={{ borderTop: '1px solid rgba(255,255,255,.18)' }}
    >
      <nav className="flex items-center gap-1" aria-label="Classroom sub-tabs">
        {CLASSROOM_TABS.map(item => {
          const isActive = item.id === activeTabId;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => selectTab(item.id)}
              aria-current={isActive ? 'page' : undefined}
              className="px-3 py-1 text-[10px] sm:text-xs font-medium whitespace-nowrap transition-all duration-200"
              style={
                isActive
                  ? {
                      borderRadius: '0.85rem',
                      background: 'var(--cp-surface)',
                      color: 'var(--cp-primary)',
                      boxShadow: 'var(--cp-clay)',
                      border: '1px solid rgba(255,255,255,.22)',
                    }
                  : {
                      borderRadius: '0.85rem',
                      background: 'rgba(255,255,255,.18)',
                      color: 'var(--cp-text)',
                      border: '1px solid rgba(255,255,255,.25)',
                    }
              }
            >
              {item.short}
            </button>
          );
        })}
      </nav>
    </div>
  );
}
