import { useEffect } from 'react';
import { useSettings } from './SettingsProvider';

/**
 * Applies the presentation settings to <html>.
 *
 * Mounted once at the app root, next to the theme effect, because both own a
 * document-level attribute and both have to be right before anything paints.
 *
 * Density and motion are applied as attributes rather than as context values so
 * that plain CSS can respond to them. Threading a "compact?" boolean through
 * every component is how two of them end up disagreeing about the spacing.
 */

/** True when the OS asks for less motion. Never throws. */
export function systemPrefersReducedMotion(): boolean {
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch {
    return false;
  }
}

/**
 * Keep <html> in step with density and motion.
 *
 * `data-motion` is reduced when *either* the setting or the OS asks for it, and
 * is removed entirely otherwise - so a student who has turned the setting off
 * but has reduced motion set at the OS level still gets the calmer behaviour,
 * which is what that OS setting is a request for.
 */
export function useDisplayPrefs(): void {
  const settings = useSettings();
  const compact = settings.get('density') === true;
  const reduceMotion = settings.get('reduce_motion') === true;

  useEffect(() => {
    document.documentElement.dataset.density = compact ? 'compact' : 'comfortable';
  }, [compact]);

  useEffect(() => {
    const root = document.documentElement;
    if (reduceMotion || systemPrefersReducedMotion()) root.dataset.motion = 'reduced';
    else delete root.dataset.motion;
  }, [reduceMotion]);
}
