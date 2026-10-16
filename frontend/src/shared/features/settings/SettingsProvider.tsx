import { createContext, useContext, useMemo, useSyncExternalStore } from 'react';
import {
  buildSnapshot,
  defaultSnapshot,
  readSettingsStore,
  subscribe,
  type SettingsStore,
} from './useSettings';

/**
 * Makes the settings store available to every screen.
 *
 * Mounted once at the app root rather than inside the Settings page, because
 * the header theme toggle and the timetable both read settings and must agree
 * with what the Settings page shows.
 */

const SettingsContext = createContext<SettingsStore | null>(null);

export function SettingsProvider({ children }: { children: React.ReactNode }) {
  const values = useSyncExternalStore(subscribe, buildSnapshot, defaultSnapshot);
  const store = useMemo(() => readSettingsStore(values), [values]);
  return <SettingsContext.Provider value={store}>{children}</SettingsContext.Provider>;
}

export function useSettings(): SettingsStore {
  const store = useContext(SettingsContext);
  if (!store) {
    throw new Error('useSettings must be used inside <SettingsProvider>');
  }
  return store;
}
