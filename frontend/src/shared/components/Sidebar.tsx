import { useAuth } from '@shared/auth/AuthWrapper';
import { useProfile } from '@shared/hooks/useProfile';
import { SECTION_ICONS } from '@shared/components/NavIcons';

interface SidebarProps {
  onClose: () => void;
  isOpen: boolean;
  onSectionChange?: (section: string) => void;
}

export function Sidebar({ onClose, isOpen, onSectionChange }: SidebarProps) {
  const { user, logout } = useAuth();
  const { programme, semester } = useProfile();

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
          className="fixed inset-0 bg-black/50 z-40 transition-opacity"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Sidebar Panel */}
      <aside
        className={`fixed top-16 right-0 h-[calc(100vh-4rem)] w-full max-w-md bg-white border-l border-gray-200 shadow-xl z-50 transition-transform duration-300 ease-in-out ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
        role="dialog"
        aria-label="User menu"
        aria-modal="true"
      >
        <div className="flex flex-col h-full p-4">
          {/* User Info Section - always visible */}
          <div className="flex flex-col gap-4 pb-4 border-b border-gray-100">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-full bg-primary-100 flex items-center justify-center">
                <span className="text-xl font-bold text-primary-600">
                  {displayName.charAt(0).toUpperCase()}
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-gray-900 truncate">{displayName}</p>
                <p className="text-sm text-gray-500 truncate">{user?.email || 'No email'}</p>
              </div>
            </div>

            {programme && !isAdmin && (
              <div className="flex items-center gap-2 text-sm">
                <span className="font-semibold text-primary-600 bg-primary-50 rounded-full px-3 py-1">
                  {programme}
                  {semester ? ` · Sem ${semester}` : ''}
                </span>
              </div>
            )}

            {isAdmin && (
              <div className="flex items-center gap-2 text-sm">
                <span className="font-semibold text-primary-600 bg-primary-50 rounded-full px-3 py-1">
                  Admin
                </span>
              </div>
            )}

            {/* Logout button - always visible at bottom of user info */}
            <button
              type="button"
              onClick={handleLogout}
              className="w-full flex items-center gap-3 px-3 py-2.5 text-sm font-medium text-danger-600 hover:bg-danger-50 rounded-lg transition-colors"
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

          {/* Profile button - navigates to profile and closes sidebar */}
          <div className="mt-auto">
            <button
              type="button"
              onClick={handleProfileNavigate}
              className="w-full flex items-center gap-3 px-3 py-2.5 text-sm font-medium text-gray-600 hover:bg-gray-50 hover:text-gray-900 rounded-lg transition-colors"
            >
              <SECTION_ICONS.profile className="w-5 h-5" />
              <span>Profile</span>
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
