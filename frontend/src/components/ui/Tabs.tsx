import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
export interface Tab {
  id: string;
  label: string;
  icon?: ReactNode;
  hue?: string;
}
const HUE: Record<string, string> = {
  // Key kept as `indigo` so the dozen call sites passing hue="indigo" need
  // no change; the value now follows the teal system palette.
  indigo: 'var(--cp-primary)',
  mint: '#047857',
  amber: '#92400E',
  coral: '#BE123C',
  sky: '#0C4A6E',
  slate: '#475569',
};
/**
 * How a tab strip presents itself.
 *
 * - `segmented` - a filled pill on a sunk container. Reads as a control you are
 *   inside, which is right for switching between whole sections.
 * - `underline`  - no container at all, just a rule under the active tab. Reads
 *   as navigation within the section you are already in, and costs no vertical
 *   space: without the pill and its padding the row is roughly a third shorter.
 */
export type TabsVariant = 'segmented' | 'underline';

export default function Tabs({
  tabs,
  active,
  onChange,
  variant = 'segmented',
}: {
  tabs: Tab[];
  active: string;
  onChange: (id: string) => void;
  variant?: TabsVariant;
}) {
  const underline = variant === 'underline';
  const listRef = useRef<HTMLDivElement>(null);
  const btnRefs = useRef(new Map<string, HTMLButtonElement>());
  const lastActiveRef = useRef<string | null>(null);
  const [indicator, setIndicator] = useState({ left: 0, width: 0, visible: false });

  // Measure the active button so the indicator slides underneath it.
  // Runs in layout effect so there is no first-paint flash at position 0.
  // The value-comparison guard matters because parents rebuild the `tabs`
  // array every render: an unconditional setState here would loop forever.
  //
  // `underline` is a dependency because it changes the chip's padding and the
  // container's own padding, which moves offsetLeft and offsetWidth. Measured on
  // `active` alone, the indicator kept the previous variant's numbers and ended
  // up as a stub under the wrong span.
  useLayoutEffect(() => {
    const btn = btnRefs.current.get(active);
    if (!btn) {
      setIndicator(prev => (prev.visible ? { ...prev, visible: false } : prev));
      return;
    }
    const left = btn.offsetLeft;
    const width = btn.offsetWidth;
    setIndicator(prev =>
      prev.left === left && prev.width === width && prev.visible
        ? prev
        : { left, width, visible: true }
    );
    // Scroll only when the active chip itself changes - never on unrelated
    // re-renders, which would fight the user's own scrolling of the row.
    if (lastActiveRef.current !== active) {
      lastActiveRef.current = active;
      // Keep the active chip in view on small screens without yanking the page.
      btn.scrollIntoView({ inline: 'nearest', block: 'nearest', behavior: 'smooth' });
    }
  }, [active, underline]);

  // Re-measure on resize/zoom; the indicator is positioned in pixels.
  useEffect(() => {
    const onResize = () => {
      const btn = btnRefs.current.get(active);
      if (btn) setIndicator({ left: btn.offsetLeft, width: btn.offsetWidth, visible: true });
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [active]);

  // Roving tabindex: arrows move between chips, Tab enters/exits the group.
  const onKeyDown = (e: React.KeyboardEvent) => {
    const i = tabs.findIndex(t => t.id === active);
    let next: number | null = null;
    if (e.key === 'ArrowRight') next = (i + 1) % tabs.length;
    else if (e.key === 'ArrowLeft') next = (i - 1 + tabs.length) % tabs.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = tabs.length - 1;
    if (next === null) return;
    e.preventDefault();
    onChange(tabs[next].id);
    btnRefs.current.get(tabs[next].id)?.focus();
  };

  return (
    <div
      ref={listRef}
      role="tablist"
      onKeyDown={onKeyDown}
      className={`relative flex gap-1 overflow-x-auto scrollbar-thin ${underline ? 'px-0.5' : 'p-0.5'}`}
      style={
        underline
          ? { borderBottom: '1px solid rgba(163,177,198,.3)' }
          : {
              borderRadius: 8,
              background: 'var(--cp-bg)',
              boxShadow: 'var(--cp-neu-inset)',
            }
      }
    >
      {/* Sliding active indicator. Killed by the global reduced-motion rule. */}
      <span
        aria-hidden
        className={`absolute transition-all duration-200 ${underline ? 'bottom-0 h-[3px]' : 'top-1 bottom-1'}`}
        style={{
          left: indicator.left,
          width: indicator.width,
          opacity: indicator.visible ? 1 : 0,
          borderRadius: underline ? 3 : 6,
          background: 'var(--cp-primary)',
          boxShadow: underline ? undefined : 'var(--cp-clay)',
        }}
      />
      {tabs.map(t => {
        const on = t.id === active;
        const hueColor = t.hue && HUE[t.hue] ? HUE[t.hue] : 'currentColor';
        return (
          <button
            key={t.id}
            ref={el => {
              if (el) btnRefs.current.set(t.id, el);
              else btnRefs.current.delete(t.id);
            }}
            role="tab"
            aria-selected={on}
            tabIndex={on ? 0 : -1}
            onClick={() => onChange(t.id)}
            className={`relative inline-flex items-center justify-center gap-2 text-sm font-medium whitespace-nowrap transition-colors duration-200 ${underline ? 'px-3' : 'px-4'}`}
            style={{
              // 36px, not the 44px the platform guidelines suggest: this strip
              // stacks under two more rows and the page reads as a wall of
              // chrome. Still comfortably above the 24px minimum, and the row
              // is horizontal, where a slightly shorter target costs less than a
              // permanently half-hidden header. The underline variant carries no
              // pill to hit, so it can go shorter still.
              minHeight: underline ? 20 : 24,
              borderRadius: 6,
              color: underline
                ? on
                  ? 'var(--cp-primary)'
                  : 'var(--cp-muted)'
                : on
                  ? 'var(--cp-on-primary)'
                  : 'var(--cp-muted)',
            }}
          >
            {t.icon ? (
              <span
                aria-hidden
                style={{
                  color: on ? (underline ? 'var(--cp-primary)' : 'var(--cp-on-primary)') : hueColor,
                  display: 'inline-flex',
                }}
              >
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
