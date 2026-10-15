import Logo from './Logo';
import { CATEGORY_NAV } from './nav';

export default function Sidebar({
  active,
  onNavigate,
  collapsed = false,
}: {
  active: string;
  onNavigate: (id: string) => void;
  collapsed?: boolean;
}) {
  return (
    <aside
      aria-label="Primary"
      className="neu-raised flex flex-col gap-2 p-4 shrink-0"
      style={{ width: collapsed ? 76 : 248 }}
    >
      <div className="mb-2">
        <Logo collapsed={collapsed} />
      </div>
      <nav className="flex flex-col gap-1.5" aria-label="Sections">
        {CATEGORY_NAV.map(n => {
          const on = n.id === active;
          return (
            <button
              key={n.id}
              type="button"
              onClick={() => onNavigate(n.id)}
              aria-current={on ? 'page' : undefined}
              title={n.label}
              className="flex items-center gap-3 px-3 py-2.5 text-sm font-medium transition-all duration-200"
              style={
                on
                  ? {
                      borderRadius: 8,
                      background: '#4F46E5',
                      color: '#fff',
                      boxShadow: 'var(--cp-clay)',
                    }
                  : { borderRadius: 8, background: 'transparent', color: 'var(--cp-muted)' }
              }
            >
              <span aria-hidden className="inline-flex shrink-0">
                {n.icon}
              </span>
              {!collapsed && <span>{n.label}</span>}
            </button>
          );
        })}
      </nav>
      {!collapsed && (
        <div className="mt-auto text-xs" style={{ color: 'var(--cp-muted)' }}>
          essential — your campus assistant
        </div>
      )}
    </aside>
  );
}
