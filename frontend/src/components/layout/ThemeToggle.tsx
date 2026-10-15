import { useEffect, useState } from 'react';
import { Moon, Sun } from 'lucide-react';

export default function ThemeToggle() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    try {
      const t = localStorage.getItem('cp-theme');
      setDark(t === 'dark' || (!t && matchMedia('(prefers-color-scheme: dark)').matches));
    } catch {
      /* ignore */
    }
  }, []);
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
    try {
      localStorage.setItem('cp-theme', dark ? 'dark' : 'light');
    } catch {
      /* ignore */
    }
  }, [dark]);
  return (
    <button
      type="button"
      onClick={() => setDark(d => !d)}
      aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
      aria-pressed={dark}
      className="neu-raised-sm inline-flex items-center justify-center rounded-full transition-all duration-200 hover:-translate-y-px active:translate-y-[1px]"
      style={{ width: 40, height: 40 }}
    >
      {dark ? <Sun size={18} aria-hidden /> : <Moon size={18} aria-hidden />}
    </button>
  );
}
