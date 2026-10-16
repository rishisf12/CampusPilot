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
import { settingsApi } from '@/api';

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
 * Two places a value can live, named per registry entry by `store`:
 *
 *  - `local`  - `shared/lib/storage`. Device-scoped and synchronous, so it is
 *               readable on the very first paint.
 *  - `server` - `/settings`. Follows the student between devices. It cannot be
 *               read synchronously, so until it arrives these entries report
 *               their registry default and the page says they are not saved yet.
 *
 * Writes are applied to the in-memory value first and then sent, so a switch
 * moves on the same frame as the click; the server response is not waited for.
 */

const LOCAL_ENTRIES = SETTINGS_REGISTRY.filter(entry => entry.store === 'local');
const SERVER_ENTRIES = SETTINGS_REGISTRY.filter(entry => entry.store === 'server');

/** Server values, once loaded. Empty until `loadServerSettings` resolves. */
let serverValues: Record<string, unknown> = {};
let serverLoaded = false;

const listeners = new Set<() => void>();

function notify(): void {
  listeners.forEach(listener => listener());
}

/**
 * Fetch the student's stored settings.
 *
 * Failure is not an error worth surfacing: the app is usable on registry
 * defaults, and a student who is offline would otherwise see an error banner for
 * a preference they did not ask to change right now.
 */
export async function loadServerSettings(): Promise<void> {
  try {
    const stored = await settingsApi.get();
    serverValues = { ...(stored || {}) };
  } catch {
    serverValues = {};
  } finally {
    serverLoaded = true;
    // The server is the truth, so the device copies are rewritten to match it -
    // otherwise a setting changed on another device would keep painting from the
    // stale local copy until this tab wrote it.
    syncMirrors();
    invalidate();
  }
}

/** Refresh the device copy of every setting that needs one before the first fetch. */
function syncMirrors(): void {
  for (const entry of SERVER_ENTRIES) {
    if (!entry.mirror) continue;
    const value = serverValues[entry.key];
    if (value === undefined) writeValue(settingStorageKey(entry.key), null);
    else writeValue(settingStorageKey(entry.key), String(value));
  }
}

/** Whether the server document has arrived. Drives the "not saved yet" marker. */
export function serverSettingsLoaded(): boolean {
  return serverLoaded;
}

/** Raw source string the cached snapshot was built from. */
function sourceKey(): string {
  const local = LOCAL_ENTRIES.map(e => `${e.key}=${readValue(settingStorageKey(e.key)) ?? ''}`);
  const server = SERVER_ENTRIES.map(e => `${e.key}=${JSON.stringify(serverValues[e.key])}`);
  return [...local, ...server].join('|');
}

/**
 * Value of a setting for the very first painted frame, before the server answers.
 *
 * A mirrored setting reads its device copy; anything else reads the registry
 * default. Either way the app renders a real value rather than a placeholder.
 */
export function bootValue(key: string): SettingsValue {
  const entry = SETTINGS_REGISTRY.find(e => e.key === key);
  if (!entry) return SETTINGS_DEFAULTS[key];
  const raw = readValue(settingStorageKey(key));
  return raw === null ? entry.default : coerceSetting(entry, raw);
}

let snapshot: Record<string, SettingsValue> | null = null;
let snapshotSource = '';

/**
 * Current value of every setting.
 *
 * Cached against the strings it was built from, because `useSyncExternalStore`
 * compares snapshots by identity - a fresh object on every call would re-render
 * every subscriber in a loop.
 */
function buildSnapshot(): Record<string, SettingsValue> {
  const source = sourceKey();
  if (snapshot && source === snapshotSource) return snapshot;

  const next: Record<string, SettingsValue> = {};
  for (const entry of SETTINGS_REGISTRY) {
    if (entry.store === 'local') {
      const raw = readValue(settingStorageKey(entry.key));
      next[entry.key] = raw === null ? entry.default : coerceSetting(entry, raw);
    } else {
      const raw = serverValues[entry.key];
      next[entry.key] = raw === undefined ? entry.default : coerceSetting(entry, raw);
    }
  }
  snapshotSource = source;
  snapshot = next;
  return next;
}

/** Snapshot used before the server document arrives, and during SSR. */
export function defaultSnapshot(): Record<string, SettingsValue> {
  return SETTINGS_DEFAULTS as Record<string, SettingsValue>;
}

function invalidate(): void {
  snapshot = null;
  snapshotSource = '';
  notify();
}

function subscribe(onChange: () => void): () => void {
  listeners.add(onChange);
  return () => {
    listeners.delete(onChange);
  };
}

/**
 * Send a server-side change, ignoring the response.
 *
 * A failure leaves the optimistic value in place: the next successful load
 * replaces it with the truth. Rolling back on failure would fight the user -
 * a switch snapping back after a dropped connection is worse than a setting
 * that has not travelled yet.
 */
function pushServer(patch: Record<string, SettingsValue | null>): void {
  settingsApi.update(patch).catch(() => {
    /* offline, or the server rejected it; the next load reconciles */
  });
}

/** Change a setting, wherever the registry says it lives. */
function writeOne(key: string, value: SettingsValue): void {
  const entry = SETTINGS_REGISTRY.find(e => e.key === key);
  if (!entry) return;

  if (entry.store === 'local') {
    writeValue(settingStorageKey(key), String(value));
    invalidate();
    return;
  }

  serverValues = { ...serverValues, [key]: value };
  // Mirrored settings are also written locally so the next cold start paints the
  // right colour before this tab has fetched anything.
  if (entry.mirror) writeValue(settingStorageKey(key), String(value));
  invalidate();
  pushServer({ [key]: value });
}

/**
 * Restore a section to its defaults.
 *
 * A local setting is removed from storage; a server one is sent as `null`,
 * which is how the endpoint expresses "drop this key" without the client
 * having to know the default.
 */
function resetSection(sectionId: SettingsSectionId): void {
  const serverPatch: Record<string, SettingsValue | null> = {};
  let touchedServer = false;

  for (const entry of settingsForSection(sectionId)) {
    if (entry.store === 'local') {
      writeValue(settingStorageKey(entry.key), null);
    } else {
      serverPatch[entry.key] = null;
      touchedServer = true;
    }
  }

  if (touchedServer) {
    serverValues = { ...serverValues };
    for (const key of Object.keys(serverPatch)) delete serverValues[key];
  }
  invalidate();
  if (touchedServer) pushServer(serverPatch);
}

/** Drop every cached value. Used on logout so the next account starts clean. */
export function clearSettingsCache(): void {
  serverValues = {};
  serverLoaded = false;
  invalidate();
}

export interface SettingsStore {
  /** Current value of a setting, coerced. Server entries report the default until loaded. */
  get(key: string): SettingsValue;
  /** Change a setting, wherever the registry says it lives. */
  set(key: string, value: SettingsValue): void;
  /** Whether the value is actually saved, as opposed to showing its default. */
  isPersisted(key: string): boolean;
  /** True when a section's settings differ from their defaults. */
  isSectionModified(sectionId: SettingsSectionId): boolean;
  /** Restore one section to its defaults. */
  resetSection(sectionId: SettingsSectionId): void;
}

export function readSettingsStore(values: Record<string, SettingsValue>): SettingsStore {
  return {
    get: (key: string): SettingsValue => {
      const entry = SETTINGS_REGISTRY.find(e => e.key === key);
      if (!entry) return SETTINGS_DEFAULTS[key];
      return values[key] ?? entry.default;
    },
    set: writeOne,
    isPersisted: key => {
      const entry = SETTINGS_REGISTRY.find(e => e.key === key);
      if (!entry) return false;
      if (entry.store === 'local') return readValue(settingStorageKey(key)) !== null;
      return serverLoaded && serverValues[key] !== undefined;
    },
    isSectionModified: sectionId =>
      settingsForSection(sectionId).some(entry => {
        const current = values[entry.key];
        if (current === entry.default) return false;
        if (entry.store === 'local') return readValue(settingStorageKey(entry.key)) !== null;
        return serverLoaded && serverValues[entry.key] !== undefined;
      }),
    resetSection,
  };
}

/** Entries the page should mark as not-yet-persisted. */
export function isPendingEntry(entry: SettingsEntry): boolean {
  return entry.store === 'server';
}

export { subscribe, buildSnapshot };
