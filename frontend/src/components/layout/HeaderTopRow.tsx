import { Menu, X } from 'lucide-react';
import { useProfile } from '@shared/hooks/useProfile';
import { greetingFor } from '@shared/lib/time';
import ThemeToggle from './ThemeToggle';

interface HeaderTopRowProps {
  online: boolean;
  sidebarOpen: boolean;
  onMenu: () => void;
}

export function HeaderTopRow({ online, sidebarOpen, onMenu }: HeaderTopRowProps) {
  const { profile } = useProfile();
  const firstName = profile?.first_name?.trim();
  const todayLabel = new Date().toLocaleDateString('en-IN', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  });

  const syncTitle = !online
    ? 'Backend offline - check your connection'
    : 'Live - backend connected';

  return (
    <header
      className="fixed top-0 left-0 right-0 z-40 md:static"
      style={{
        background: 'var(--cp-chrome)',
        borderBottom: '1px solid rgba(255,255,255,.12)',
      }}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between gap-2 h-16">
          {/* Greeting */}
          <div className="flex-1 min-w-0 text-center sm:text-left px-1">
            <p
              className="text-sm font-semibold truncate"
              style={{ color: 'var(--cp-chrome-text)' }}
            >
              {greetingFor()}
              {firstName ? `, ${firstName}` : ''}
            </p>
            <p className="text-xs truncate" style={{ color: 'var(--cp-chrome-muted)' }}>
              {todayLabel}
            </p>
          </div>

          {/* Right side: status + theme + menu */}
          <div className="flex items-center gap-2 shrink-0">
            <span
              className="w-2.5 h-2.5 rounded-full"
              style={{
                background: online ? 'var(--cp-success)' : 'var(--cp-danger)',
              }}
              title={syncTitle}
              aria-label={syncTitle}
              role="status"
            />
            <ThemeToggle />
            <button
              type="button"
              onClick={onMenu}
              className="w-10 h-10 flex items-center justify-center transition-all duration-200"
              style={
                sidebarOpen
                  ? {
                      borderRadius: 16,
                      background: 'var(--cp-primary)',
                      color: 'var(--cp-on-primary)',
                      boxShadow: 'var(--cp-clay)',
                    }
                  : {
                      borderRadius: 16,
                      /* Header-matching glass instead of the white pill. */
                      background: 'rgba(255,255,255,.16)',
                      color: 'var(--cp-chrome-text)',
                      border: '1px solid rgba(255,255,255,.28)',
                    }
              }
              aria-label={sidebarOpen ? 'Close menu' : 'Open menu'}
              aria-expanded={sidebarOpen}
            >
              {sidebarOpen ? (
                <X
                  size={24}
                  strokeWidth={2}
                  aria-hidden
                  className="transition-transform duration-200"
                />
              ) : (
                <Menu
                  size={24}
                  strokeWidth={2}
                  aria-hidden
                  className="transition-transform duration-200"
                />
              )}
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
