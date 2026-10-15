import { LogOut } from 'lucide-react';
import { useAuth } from '@shared/auth/AuthWrapper';
import { useProfile } from '@shared/hooks/useProfile';
import { SECTION_ICONS } from '@shared/components/NavIcons';
import { Badge } from '@/components/ui';

interface SidebarProps {
  onClose: () => void;
  isOpen: boolean;
  onSectionChange?: (section: string) => void;
}

export function Sidebar({ onClose, isOpen, onSectionChange }: SidebarProps) {
  const { user, logout } = useAuth();
  const { programme, semester, branch } = useProfile();
  const displayName =
    user?.full_name?.trim() || user?.username || user?.email?.split('@')[0] || 'Student';
  const isAdmin = user?.role === 'admin';

  const handleProfileNavigate = () => {
    if (onSectionChange) onSectionChange('profile');
    onClose();
  };
  const handleLogout = () => {
    logout();
    onClose();
  };
  const ProfileIcon = SECTION_ICONS.profile;

  return (
    <>
      {isOpen && (
        <div className="fixed inset-0 bg-black/30 z-40" onClick={onClose} aria-hidden="true" />
      )}
      <aside
        className={`neu-raised fixed top-0 right-0 h-full w-80 z-50 transition-transform duration-200 ease-out flex flex-col ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}
        role="dialog"
        aria-label="User menu"
        aria-modal="true"
        style={{ borderRadius: '24px 0 0 24px' }}
      >
        <div className="p-4" style={{ borderBottom: '1px solid rgba(163,177,198,.25)' }}>
          <div className="flex items-center gap-3">
            <div
              className="neu-raised-sm flex items-center justify-center shrink-0"
              style={{ width: 40, height: 40, borderRadius: '50%' }}
            >
              <span className="text-lg font-bold" style={{ color: 'var(--cp-primary)' }}>
                {displayName.charAt(0).toUpperCase()}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-semibold truncate" style={{ color: 'var(--cp-text)' }}>
                {displayName}
              </p>
              <p className="text-xs truncate" style={{ color: 'var(--cp-muted)' }}>
                {user?.email || 'No email'}
              </p>
            </div>
          </div>
          {!isAdmin && (
            <div className="mt-4 grid grid-cols-3 gap-2">
              {(
                [
                  ['Programme', programme],
                  ['Semester', semester],
                  ['Branch', branch],
                ] as const
              ).map(([k, v]) => (
                <div key={k}>
                  <p
                    className="text-[10px] uppercase tracking-wide mb-1"
                    style={{ color: 'var(--cp-muted)' }}
                  >
                    {k}
                  </p>
                  <p className="text-sm font-semibold truncate" style={{ color: 'var(--cp-text)' }}>
                    {v || '—'}
                  </p>
                </div>
              ))}
            </div>
          )}
          {isAdmin && (
            <div className="mt-3">
              <Badge tone="primary">Admin</Badge>
            </div>
          )}
        </div>
        <nav className="flex-1 overflow-y-auto p-4 space-y-1" aria-label="User">
          <button
            type="button"
            onClick={handleProfileNavigate}
            className="w-full flex items-center gap-3 px-3 py-2.5 text-sm font-medium rounded-2xl transition-all duration-200"
            style={{ color: 'var(--cp-text)' }}
          >
            <ProfileIcon className="w-5 h-5" />
            <span>Profile</span>
          </button>
        </nav>
        <div className="p-4" style={{ borderTop: '1px solid rgba(163,177,198,.25)' }}>
          <button
            type="button"
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3 py-2.5 text-sm font-medium rounded-2xl transition-all duration-200"
            style={{ color: 'var(--cp-danger)' }}
          >
            <LogOut size={20} strokeWidth={2} aria-hidden />
            <span>Logout</span>
          </button>
        </div>
      </aside>
    </>
  );
}
