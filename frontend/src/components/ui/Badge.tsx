import type { HTMLAttributes } from 'react';
type Tone = 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'neutral';
const bg: Record<Tone, string> = {
  primary: '#EEF2FF',
  success: '#D1FAE5',
  warning: '#FEF3C7',
  danger: '#FEE2E2',
  info: '#E0F2FE',
  neutral: 'var(--cp-surface)',
};
const fg: Record<Tone, string> = {
  primary: '#4338CA',
  success: '#047857',
  warning: '#92400E',
  danger: '#B91C1C',
  info: '#0C4A6E',
  neutral: 'var(--cp-muted)',
};
export default function Badge({
  tone = 'neutral',
  className = '',
  style,
  ...rest
}: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-3 py-1 text-xs font-semibold rounded-full ${className}`}
      style={{
        background: bg[tone],
        color: fg[tone],
        boxShadow: 'var(--cp-neu-raised-sm)',
        border: '1px solid rgba(163,177,198,.3)',
        ...style,
      }}
      {...rest}
    />
  );
}
