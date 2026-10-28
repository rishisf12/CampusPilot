import { Bell, Search } from 'lucide-react';
import { useState } from 'react';
import Logo from './Logo';
import ThemeToggle from './ThemeToggle';

export default function Navbar({
  online,
  onMenu,
  sidebarOpen,
  onSearch,
}: {
  online: boolean;
  onMenu: () => void;
  sidebarOpen: boolean;
  onSearch?: (q: string) => void;
}) {
  const [q, setQ] = useState('');
  return (
    <header className="neu-raised-sm sticky top-0 z-40 px-6 py-4">
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={onMenu}
          aria-label={sidebarOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={sidebarOpen}
          className="neu-raised-sm inline-flex items-center justify-center rounded-xl"
          style={{ width: 44, height: 44 }}
        >
          <svg
            width="22"
            height="22"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            aria-hidden
          >
            {sidebarOpen ? (
              <>
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </>
            ) : (
              <>
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </>
            )}
          </svg>
        </button>
        <Logo />
        <div className="flex-1 max-w-2xl">
          <label className="sr-only" htmlFor="global-search">
            Search
          </label>
          <div className="neu-inset flex items-center gap-2 px-3 py-2">
            <Search size={18} aria-hidden style={{ color: 'var(--cp-muted)' }} />
            <input
              id="global-search"
              value={q}
              onChange={e => {
                setQ(e.target.value);
                onSearch?.(e.target.value);
              }}
              placeholder="Search schedule, rooms, exams…"
              className="w-full bg-transparent text-sm outline-none"
              style={{ color: 'var(--cp-text)' }}
            />
          </div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span
            className="inline-block rounded-full"
            style={{
              width: 10,
              height: 10,
              background: online ? 'var(--cp-success)' : 'var(--cp-danger)',
            }}
            title={online ? 'Backend connected' : 'Backend offline'}
            role="status"
            aria-label={online ? 'Backend connected' : 'Backend offline'}
          />
          <button
            type="button"
            aria-label="Notifications"
            className="neu-raised-sm inline-flex items-center justify-center rounded-full"
            style={{ width: 40, height: 40 }}
          >
            <Bell size={18} aria-hidden />
          </button>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
