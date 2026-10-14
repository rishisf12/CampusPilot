import { useAuth } from '@shared/auth/AuthWrapper';
import { useProfile } from '@shared/hooks/useProfile';
import { SECTION_ICONS } from '@shared/components/NavIcons';

interface SidebarProps {
  onClose: () => void;
  isOpen: boolean;
  onSectionChange?: (section: string) => void;
}

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
    if (onSectionChange) {
      onSectionChange('profile');
    }
    onClose();
  };

  const handleLogout = () => {
    logout();
    onClose();
  };

  return (
    <>
      {/* Overlay - closes sidebar on click */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-40 transition-opacity duration-300"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Sidebar Panel */}
      <aside
        className={`fixed top-0 right-0 h-full w-80 bg-white border-l border-gray-200 shadow-2xl z-50 transition-transform duration-300 ease-in-out flex flex-col ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
        role="dialog"
        aria-label="User menu"
        aria-modal="true"
      >
        {/* User Info Section */}
        <div className="p-4 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center shrink-0">
              <span className="text-lg font-bold text-primary-600">
                {displayName.charAt(0).toUpperCase()}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-gray-900 truncate">{displayName}</p>
              <p className="text-xs text-gray-500 truncate">{user?.email || 'No email'}</p>
            </div>
          </div>

          {/* Programme, Semester, Branch in single row */}
          {!isAdmin && (
            <div className="mt-4 grid grid-cols-3 gap-2">
              <div>
                <p className="text-[10px] uppercase tracking-wide text-gray-400 mb-1">Programme</p>
                <p className="text-sm font-semibold text-gray-900 truncate">{programme || '—'}</p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wide text-gray-400 mb-1">Semester</p>
                <p className="text-sm font-semibold text-gray-900 truncate">{semester || '—'}</p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wide text-gray-400 mb-1">Branch</p>
                <p className="text-sm font-semibold text-gray-900 truncate">{branch || '—'}</p>
              </div>
            </div>
          )}

          {isAdmin && (
            <div className="mt-3">
              <span className="inline-block text-xs font-semibold text-primary-600 bg-primary-50 rounded-full px-3 py-1">
                Admin
              </span>
            </div>
          )}
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 overflow-y-auto p-4 space-y-1">
          <button
            type="button"
            onClick={handleProfileNavigate}
            className="w-full flex items-center gap-3 px-3 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 hover:text-gray-900 rounded-lg transition-colors"
          >
            <SECTION_ICONS.profile className="w-5 h-5" />
            <span>Profile</span>
          </button>
        </nav>

        {/* Logout button - fixed at bottom */}
        <div className="p-4 border-t border-gray-100">
          <button
            type="button"
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3 py-2.5 text-sm font-medium text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          >
            <svg
              className="w-5 h-5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            <span>Logout</span>
          </button>
        </div>
      </aside>
    </>
  );
}
