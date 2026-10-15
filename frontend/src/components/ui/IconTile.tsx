import type { HTMLAttributes } from 'react';
type Hue = 'indigo' | 'mint' | 'amber' | 'coral' | 'sky' | 'slate';
const tile: Record<Hue, string> = {
  // `indigo` key kept for the existing call sites. Soft teal via color-mix so
  // it adapts to both themes automatically, like the other soft tints.
  indigo: 'color-mix(in srgb, var(--cp-primary) 12%, transparent)',
  mint: '#D1FAE5',
  amber: '#FEF3C7',
  coral: '#FFE4E6',
  sky: '#E0F2FE',
  slate: 'var(--cp-surface)',
};
const ic: Record<Hue, string> = {
  indigo: 'var(--cp-primary)',
  mint: '#047857',
  amber: '#92400E',
  coral: '#BE123C',
  sky: '#0C4A6E',
  slate: 'var(--cp-text)',
};
export default function IconTile({
  hue = 'indigo',
  size = 44,
  className = '',
  style,
  ...rest
}: HTMLAttributes<HTMLDivElement> & { hue?: Hue; size?: number }) {
  return (
    <div
      className={`inline-flex items-center justify-center shrink-0 ${className}`}
      style={{
        width: size,
        height: size,
        borderRadius: 10,
        background: tile[hue],
        color: ic[hue],
        boxShadow: 'var(--cp-clay)',
        border: '1px solid rgba(163,177,198,.3)',
        ...style,
      }}
      {...rest}
    />
  );
}
