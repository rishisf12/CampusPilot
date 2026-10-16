import type { SettingsEntry, SettingsSectionId } from '@shared/constants';
import { settingsForSection } from '@shared/constants';
import SettingRow from '../SettingRow';
import { useSettings } from '../SettingsProvider';
import { serverSettingsLoaded } from '../useSettings';
import type { AccountPaneProps } from '../sections/AccountSection';
import type { Pane } from './panes';

export interface SettingsPaneProps {
  pane: Pane;
  sectionId: SettingsSectionId;
  /** Forwarded to a custom pane; ignored by registry panes. */
  accountProps?: AccountPaneProps;
}

/**
 * One pane of the Settings page.
 *
 * `registry` panes are rendered straight from `settingsForSection`, so adding an
 * entry to the registry is enough for it to appear with a correctly typed
 * control, a label and a saved-state marker. `custom` panes hold real content
 * rather than fields - Account being the one.
 */
export default function SettingsPane({ pane, sectionId, accountProps }: SettingsPaneProps) {
  const settings = useSettings();

  if (pane.kind === 'custom') {
    return <>{pane.render(accountProps ?? {})}</>;
  }

  const entries: readonly SettingsEntry[] = settingsForSection(sectionId);
  const modified = settings.isSectionModified(sectionId);
  const waitingForServer = entries.some(e => e.store === 'server') && !serverSettingsLoaded();

  return (
    <div className="rounded-3xl p-5" style={{ background: 'var(--cp-surface)' }}>
      <div className="flex items-center justify-between gap-3 mb-1">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--cp-text)' }}>
          {entries.length === 1 ? '1 setting' : `${entries.length} settings`}
        </h3>
        <button
          type="button"
          onClick={() => settings.resetSection(sectionId)}
          disabled={!modified}
          className="text-xs font-medium px-3 py-1.5 rounded-full transition-all duration-200 disabled:opacity-40"
          style={{
            color: 'var(--cp-muted)',
            background: 'var(--cp-bg)',
            border: '1px solid rgba(163,177,198,.3)',
          }}
        >
          Reset to defaults
        </button>
      </div>
      <p className="text-xs mb-2" style={{ color: 'var(--cp-muted)' }}>
        {waitingForServer
          ? 'Loading your saved settings…'
          : 'Changes save as you make them - there is no save button.'}
      </p>
      <div>
        {entries.map(entry => (
          <SettingRow key={entry.key} entry={entry} />
        ))}
      </div>
    </div>
  );
}
