import { useState } from 'react';
import Navbar from './Navbar';
import Sidebar from './Sidebar';

export default function LayoutShell({
  active,
  online,
  onNavigate,
  children,
}: {
  active: string;
  online: boolean;
  onNavigate: (id: string) => void;
  children: React.ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  return (
    <div className="min-h-screen flex flex-col gap-4 p-4" style={{ background: 'var(--cp-bg)' }}>
      <Navbar
        online={online}
        sidebarOpen={!collapsed}
        onMenu={() => {
          setCollapsed(c => !c);
          setMobileOpen(o => !o);
        }}
      />
      <div className="flex gap-4 flex-1">
        <div className="hidden md:block">
          <Sidebar active={active} onNavigate={onNavigate} collapsed={collapsed} />
        </div>
        {mobileOpen && (
          <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-label="Navigation">
            <div
              className="absolute inset-0"
              style={{ background: 'rgba(27,31,42,.45)' }}
              onClick={() => setMobileOpen(false)}
              aria-hidden
            />
            <div className="absolute left-4 top-4 bottom-4 overflow-y-auto">
              <Sidebar
                active={active}
                onNavigate={id => {
                  onNavigate(id);
                  setMobileOpen(false);
                }}
              />
            </div>
          </div>
        )}
        <main className="flex-1 min-w-0">{children}</main>
      </div>
      <footer className="text-center text-xs" style={{ color: 'var(--cp-muted)' }}>
        essential — your campus assistant
      </footer>
    </div>
  );
}
