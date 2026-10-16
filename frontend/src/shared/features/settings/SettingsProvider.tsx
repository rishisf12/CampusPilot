import { createContext, useContext, useEffect, useMemo, useSyncExternalStore } from 'react';
import {
  buildSnapshot,
  clearSettingsCache,
  defaultSnapshot,
  loadServerSettings,
  readSettingsStore,
  subscribe,
  type SettingsStore,
} from './useSettings';

/**
 * Makes the settings store available to every screen.
 *
 * Mounted once at the app root rather than inside the Settings page, because the
 * header theme toggle and the timetable both read settings and must agree with
 * what the Settings page shows.
 *
 * The server document is fetched once here. It is deliberately not awaited before
 * rendering: a student offline would otherwise stare at a blank screen over a
 * preference, and every entry has a working default to render instead.
 */

const SettingsContext = createContext<SettingsStore | null>(null);

export function SettingsProvider({ children }: { children: React.ReactNode }) {
  const values = useSyncExternalStore(subscribe, buildSnapshot, defaultSnapshot);
  const store = useMemo(() => readSettingsStore(values), [values]);

  useEffect(() => {
    void loadServerSettings();
  }, []);

  // The server document belongs to whoever is signed in, so signing out has to
  // drop it - otherwise the next account would briefly see the previous one's
  // settings, including the theme.
  useEffect(() => {
    const onSignedOut = () => clearSettingsCache();
    window.addEventListener('cp:signed-out', onSignedOut);
    return () => window.removeEventListener('cp:signed-out', onSignedOut);
  }, []);

  return <SettingsContext.Provider value={store}>{children}</SettingsContext.Provider>;
}

export function useSettings(): SettingsStore {
  const store = useContext(SettingsContext);
  if (!store) {
    throw new Error('useSettings must be used inside <SettingsProvider>');
  }
  return store;
}
