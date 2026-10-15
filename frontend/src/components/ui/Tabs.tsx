import type { ReactNode } from 'react';
export interface Tab {
  id: string;
  label: string;
  icon?: ReactNode;
  hue?: string;
}
const HUE: Record<string, string> = {
  indigo: '#4338CA',
  mint: '#047857',
  amber: '#92400E',
  coral: '#BE123C',
  sky: '#0C4A6E',
  slate: '#475569',
};
export default function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: Tab[];
  active: string;
  onChange: (id: string) => void;
}) {
  return (
    <div
      role="tablist"
      className="flex gap-2 p-1.5"
      style={{ borderRadius: 8, background: 'var(--cp-bg)', boxShadow: 'var(--cp-neu-inset)' }}
    >
      {tabs.map(t => {
        const on = t.id === active;
        const hueColor = t.hue && HUE[t.hue] ? HUE[t.hue] : 'currentColor';
        return (
          <button
            key={t.id}
            role="tab"
            aria-selected={on}
            onClick={() => onChange(t.id)}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium transition-all duration-200"
            style={
              on
                ? {
                    borderRadius: 6,
                    background: '#4F46E5',
                    color: '#fff',
                    boxShadow: 'var(--cp-clay)',
                  }
                : { borderRadius: 6, background: 'transparent', color: 'var(--cp-muted)' }
            }
          >
            {t.icon ? (
              <span aria-hidden style={{ color: on ? '#fff' : hueColor, display: 'inline-flex' }}>
                {t.icon}
              </span>
            ) : null}
            {t.label}
          </button>
        );
      })}
    </div>
  );
}
