import { useEffect } from 'react';
import { readValue } from '@shared/lib/storage';
import { useSettings } from './SettingsProvider';

/**
 * Applies the `theme` setting to the document.
 *
 * Mounted once at the app root. The header toggle and the Settings page both go
 * through this one effect, so exactly one place owns the `dark` class. Before
 * this, `ThemeToggle` wrote `cp-theme` and kept its own boolean - a Settings
 * page could not have shown the real value without reimplementing that.
 *
 * `'system'` follows the OS and keeps following it: the media query stays
 * subscribed, so a laptop that switches to dark at sunset repaints the app
 * without a reload.
 */

/** True when the OS is asking for dark. Never throws. */
export function systemPrefersDark(): boolean {
  try {
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  } catch {
    return false;
  }
}

/** Resolve a `theme` setting to the class that should be on <html>. */
function resolve(theme: string, override?: 'light' | 'dark'): 'light' | 'dark' {
  if (override) return override;
  if (theme === 'light' || theme === 'dark') return theme;
  return systemPrefersDark() ? 'dark' : 'light';
}

/**
 * Keeps <html> in step with the theme setting, and returns the setting.
 *
 * The `system` branch re-reads the media query on change rather than only at
 * mount, so the OS changing its mind is enough to repaint.
 */
export function useApplyTheme(): string {
  const theme = String(useSettings().get('theme'));

  useEffect(() => {
    const isSystem = theme !== 'light' && theme !== 'dark';
    const apply = () => {
      const next = isSystem
        ? systemPrefersDark()
          ? 'dark'
          : 'light'
        : (theme as 'light' | 'dark');
      document.documentElement.classList.toggle('dark', next === 'dark');
    };
    apply();

    if (!isSystem) return;
    let mq: MediaQueryList;
    try {
      mq = window.matchMedia('(prefers-color-scheme: dark)');
    } catch {
      return;
    }
    mq.addEventListener('change', apply);
    return () => mq.removeEventListener('change', apply);
  }, [theme]);

  return theme;
}

/**
 * Flips between light and dark from the header.
 *
 * A toggle has two positions, so it cannot express `'system'`. Pressing it while
 * on `'system'` pins the theme the user is currently looking at - which is what
 * they asked for - rather than inverting to a value that may already be active.
 */
export function useThemeToggle(): {
  active: 'light' | 'dark';
  toggle: () => void;
} {
  const settings = useSettings();
  const theme = String(settings.get('theme'));
  const resolved = resolve(theme);
  return {
    active: resolved,
    toggle: () => settings.set('theme', resolved === 'dark' ? 'light' : 'dark'),
  };
}

/**
 * Apply the stored theme before React mounts.
 *
 * Reads storage directly rather than going through the store: the first paint
 * has to be right, and waiting for a hook means a white flash on every reload
 * for a dark-mode user.
 *
 * Tolerant of an older build's value - anything that is not 'dark' is treated as
 * light, which is what the previous toggle assumed too.
 */
export function bootstrapTheme(): void {
  const stored = readValue('cp-theme');
  const dark = stored === 'dark' || (stored === null && systemPrefersDark());
  document.documentElement.classList.toggle('dark', dark);
}
