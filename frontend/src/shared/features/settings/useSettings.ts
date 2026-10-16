import {
  SETTINGS_DEFAULTS,
  SETTINGS_REGISTRY,
  coerceSetting,
  settingsForSection,
  type SettingsEntry,
  type SettingsSectionId,
  type SettingsValue,
} from '@shared/constants';
import { readValue, settingStorageKey, writeValue } from '@shared/lib/storage';

/**
 * User settings, one store shared by every screen that reads them.
 *
 * `useSyncExternalStore` rather than context-plus-state: a setting has to be
 * readable by the header toggle, the timetable and the Settings page at once,
 * and all three must repaint the moment it changes. A store outside React plus a
 * subscription satisfies that without a provider re-rendering the tree on every
 * keystroke, and without the stale-copy bugs a plain module-level cache would
 * have.
 *
 * Only `store: 'local'` entries resolve today. The `server` entries in the
 * registry read their default and are shown as "not saved yet" - they are
 * declared in Phase 0 so the page shows the full shape of the settings and each
 * one switches on when persistence lands, rather than the list being rewritten.
 */

/** Read one value, coerced to its declared type. */
function readOne(entry: SettingsEntry): SettingsValue {
  const raw = readValue(settingStorageKey(entry.key));
  return raw === null ? entry.default : coerceSetting(entry, raw);
}

/**
 * The current value of every `local` setting.
 *
 * Cached against the raw strings it was built from, because
 * `useSyncExternalStore` compares snapshots by identity - returning a fresh
 * object on every call would re-render every subscriber in a loop.
 */
let snapshot: Record<string, SettingsValue> | null = null;
let snapshotSource = '';

function buildSnapshot(): Record<string, SettingsValue> {
  const source = SETTINGS_REGISTRY.filter(e => e.store === 'local')
    .map(e => `${e.key}=${readValue(settingStorageKey(e.key)) ?? ''}`)
    .join('|');
  if (snapshot && source === snapshotSource) return snapshot;
  const next: Record<string, SettingsValue> = {};
  for (const entry of SETTINGS_REGISTRY) {
    if (entry.store === 'local') next[entry.key] = readOne(entry);
  }
  snapshotSource = source;
  snapshot = next;
  return next;
}

const listeners = new Set<() => void>();

function subscribe(onChange: () => void): () => void {
  listeners.add(onChange);
  return () => {
    listeners.delete(onChange);
  };
}

/** Snapshot used on the server render and as the fallback when storage is absent. */
export function defaultSnapshot(): Record<string, SettingsValue> {
  return SETTINGS_DEFAULTS as Record<string, SettingsValue>;
}

/**
 * Persist a setting and tell every subscriber.
 *
 * The snapshot is invalidated after the write, not before: it is derived from
 * storage, so rebuilding before the write would rebuild from the old value and
 * the switch would visibly snap back.
 */
function writeOne(key: string, value: SettingsValue): void {
  const entry = SETTINGS_REGISTRY.find(e => e.key === key);
  if (!entry || entry.store !== 'local') return;
  writeValue(settingStorageKey(key), String(value));
  snapshot = null;
  snapshotSource = '';
  listeners.forEach(notify => notify());
}

/** Put a section's local settings back to their registry defaults. */
function resetSection(sectionId: SettingsSectionId): void {
  for (const entry of settingsForSection(sectionId)) {
    if (entry.store === 'local') writeValue(settingStorageKey(entry.key), null);
  }
  snapshot = null;
  snapshotSource = '';
  listeners.forEach(notify => notify());
}

export interface SettingsStore {
  /** Current value of a setting, coerced. Server-backed ones return the default. */
  get(key: string): SettingsValue;
  /** Change a setting. A no-op for `server` entries until persistence lands. */
  set(key: string, value: SettingsValue): void;
  /** Whether the value is actually saved, as opposed to showing its default. */
  isPersisted(key: string): boolean;
  /** True when a section's local settings differ from their defaults. */
  isSectionModified(sectionId: SettingsSectionId): boolean;
  /** Restore one section's local settings to their defaults. */
  resetSection(sectionId: SettingsSectionId): void;
}

export function readSettingsStore(values: Record<string, SettingsValue>): SettingsStore {
  const get = (key: string): SettingsValue => {
    const entry = SETTINGS_REGISTRY.find(e => e.key === key);
    if (!entry) return SETTINGS_DEFAULTS[key];
    return values[key] ?? entry.default;
  };
  return {
    get,
    set: writeOne,
    isPersisted: key => {
      const entry = SETTINGS_REGISTRY.find(e => e.key === key);
      return !!entry && entry.store === 'local' && readValue(settingStorageKey(key)) !== null;
    },
    isSectionModified: sectionId =>
      settingsForSection(sectionId).some(
        entry =>
          entry.store === 'local' &&
          readValue(settingStorageKey(entry.key)) !== null &&
          values[entry.key] !== entry.default
      ),
    resetSection,
  };
}

export { subscribe, buildSnapshot };
