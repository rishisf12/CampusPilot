import { Moon, Sun } from 'lucide-react';
import { useThemeToggle } from '@shared/features/settings/useTheme';

/**
 * Header theme button.
 *
 * Reads and writes the shared `theme` setting rather than a private
 * `cp-theme` string, so it can never disagree with the Appearance pane in
 * Settings: both go through one store and one effect that owns the `dark` class.
 */
export default function ThemeToggle() {
  const { active, toggle } = useThemeToggle();
  const dark = active === 'dark';
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
      aria-pressed={dark}
      className="neu-raised-sm inline-flex items-center justify-center rounded-full transition-all duration-200 hover:-translate-y-px active:translate-y-[1px] active:scale-[0.98]"
      style={{ width: 44, height: 44 }}
    >
      {dark ? <Sun size={18} aria-hidden /> : <Moon size={18} aria-hidden />}
    </button>
  );
}
