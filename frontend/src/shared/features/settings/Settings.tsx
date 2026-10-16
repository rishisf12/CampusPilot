import { useState } from 'react';
import { SETTINGS_SECTIONS, type SettingsSectionId } from '@shared/constants';
import SettingsPane from './panes/SettingsPane';
import { PANES } from './panes/panes';
import SettingsSearch, { SettingsSearchInput } from './SettingsSearch';

export interface SettingsProps {
  /**
   * Opens the module's Profile page.
   *
   * Passed in because shared/ may not reach a module's section setter. Without
   * it the Account pane says where Profile lives instead of offering a control
   * that does nothing.
   */
  onOpenProfile?: () => void;
}

/**
 * The Settings page.
 *
 * Reached from the sidebar in every module - the same page whether the user is
 * UG, PG or an admin, because settings belong to the person, not the bundle.
 *
 * Tabs rather than one long scroll: four short groups of unrelated controls read
 * badly stacked, because "what does this switch do" loses its neighbours. A tab
 * keeps each group whole and stays one tap from any other.
 */
export default function Settings({ onOpenProfile }: SettingsProps) {
  const [active, setActive] = useState<SettingsSectionId>('appearance');
  const [query, setQuery] = useState('');
  const section = SETTINGS_SECTIONS.find(s => s.id === active) ?? SETTINGS_SECTIONS[0];
  // One character matches nearly everything, which reads as "search is broken".
  const searching = query.trim().length >= 2;

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold" style={{ color: 'var(--cp-text)' }}>
          Settings
        </h2>
        <p className="text-sm mt-1" style={{ color: 'var(--cp-muted)' }}>
          How the app looks and behaves, on this account and this device.
        </p>
      </div>

      <SettingsSearchInput value={query} onChange={setQuery} />

      {searching ? (
        <SettingsSearch query={query} />
      ) : (
        <>
          <div
            role="tablist"
            aria-label="Settings sections"
            className="flex items-center gap-1 p-1 rounded-full overflow-x-auto"
            style={{ background: 'var(--cp-bg)', boxShadow: 'var(--cp-neu-inset)' }}
          >
            {SETTINGS_SECTIONS.map(item => {
              const isActive = item.id === active;
              return (
                <button
                  key={item.id}
                  type="button"
                  role="tab"
                  id={`settings-tab-${item.id}`}
                  aria-selected={isActive}
                  aria-controls={`settings-panel-${item.id}`}
                  tabIndex={isActive ? 0 : -1}
                  onClick={() => setActive(item.id)}
                  onKeyDown={e => {
                    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
                    e.preventDefault();
                    const i = SETTINGS_SECTIONS.findIndex(s => s.id === active);
                    const delta = e.key === 'ArrowRight' ? 1 : -1;
                    const next = (i + delta + SETTINGS_SECTIONS.length) % SETTINGS_SECTIONS.length;
                    setActive(SETTINGS_SECTIONS[next].id);
                  }}
                  className="px-3.5 py-2 text-sm font-medium rounded-full transition-all duration-200 whitespace-nowrap shrink-0"
                  style={
                    isActive
                      ? {
                          background: 'var(--cp-primary)',
                          color: 'var(--cp-on-primary)',
                          boxShadow: 'var(--cp-clay)',
                        }
                      : { color: 'var(--cp-muted)' }
                  }
                >
                  {item.label}
                </button>
              );
            })}
          </div>

          <div
            role="tabpanel"
            id={`settings-panel-${section.id}`}
            aria-labelledby={`settings-tab-${section.id}`}
            tabIndex={0}
            className="space-y-3"
          >
            <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
              {section.blurb}
            </p>
            {section.note && (
              <p
                className="text-xs px-3 py-2 rounded-2xl"
                style={{ background: 'var(--cp-bg)', color: 'var(--cp-muted)' }}
              >
                {section.note}
              </p>
            )}
            <SettingsPane
              pane={PANES[section.id]}
              sectionId={section.id}
              accountProps={{ onOpenProfile }}
            />
          </div>
        </>
      )}
    </div>
  );
}
