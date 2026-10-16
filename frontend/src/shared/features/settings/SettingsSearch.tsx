import { useMemo } from 'react';
import { SETTINGS_SECTIONS, SETTINGS_REGISTRY, type SettingsEntry } from '@shared/constants';
import SettingRow from './SettingRow';

/**
 * Search across every setting at once.
 *
 * Searching *inside* the active tab was the obvious first design and the wrong
 * one: "week" matches something in Schedule, "dark" something in Appearance, and a
 * student who types "light" into the Notifications tab is told nothing matches
 * while three settings elsewhere say exactly what they wanted. Results are
 * grouped by section instead, so a search can span the whole page.
 *
 * Matching is on the words a student would type, not on keys: the label, the help
 * text and the option names. A key like `week_start` is an implementation
 * detail nobody types.
 */
export default function SettingsSearch({ query }: { query: string }) {
  const trimmed = query.trim().toLowerCase();

  const groups = useMemo(() => {
    if (trimmed.length < 2) return [];
    return SETTINGS_SECTIONS.map(section => ({
      section,
      entries: SETTINGS_REGISTRY.filter(entry => entry.section === section.id).filter(entry =>
        matches(entry, trimmed)
      ),
    })).filter(group => group.entries.length > 0);
  }, [trimmed]);

  if (trimmed.length < 2) return null;

  return (
    <div className="space-y-3">
      {groups.length === 0 ? (
        <p
          className="text-sm px-4 py-6 rounded-2xl text-center"
          style={{ background: 'var(--cp-surface)', color: 'var(--cp-muted)' }}
        >
          Nothing matches &ldquo;{query.trim()}&rdquo;.
        </p>
      ) : (
        groups.map(({ section, entries }) => (
          <div
            key={section.id}
            className="rounded-3xl p-5"
            style={{ background: 'var(--cp-surface)' }}
          >
            <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--cp-text)' }}>
              {section.label}
            </h3>
            <div>
              {entries.map((entry: SettingsEntry) => (
                <SettingRow key={entry.key} entry={entry} />
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  );
}

/** Does this setting match what the student typed? */
function matches(entry: SettingsEntry, query: string): boolean {
  const haystack = [entry.label, entry.help, ...(entry.choices?.map(c => c.label) ?? [])]
    .join(' ')
    .toLowerCase();
  return haystack.includes(query);
}

/** The search box itself, so Settings.tsx can control where it renders. */
export function SettingsSearchInput({
  value,
  onChange,
}: {
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <input
      type="search"
      value={value}
      onChange={event => onChange(event.target.value)}
      placeholder="Search settings"
      aria-label="Search settings"
      className="w-full px-4 py-2.5 text-sm rounded-2xl"
      style={{
        background: 'var(--cp-surface)',
        color: 'var(--cp-text)',
        boxShadow: 'var(--cp-neu-inset)',
        border: '1px solid rgba(163,177,198,.3)',
      }}
    />
  );
}
