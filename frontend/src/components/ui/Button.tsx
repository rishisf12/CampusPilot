import { Loader2 } from 'lucide-react';
import type { ButtonHTMLAttributes } from 'react';

type Variant = 'primary' | 'secondary' | 'success' | 'danger' | 'ghost';
type Size = 'sm' | 'md' | 'lg';

const sizes: Record<Size, { pad: string; text: string; icon: number }> = {
  sm: { pad: 'px-3 py-1.5', text: 'text-sm', icon: 16 },
  md: { pad: 'px-4 py-2', text: 'text-[15px]', icon: 18 },
  lg: { pad: 'px-5 py-2.5', text: 'text-base', icon: 20 },
};

const fills: Record<Variant, string> = {
  primary:
    'background:#4F46E5;color:#fff;border:1px solid #4F46E5;box-shadow:0 1px 2px rgba(15,23,42,.1);',
  success:
    'background:#16A34A;color:#fff;border:1px solid #16A34A;box-shadow:0 1px 2px rgba(15,23,42,.1);',
  danger:
    'background:#DC2626;color:#fff;border:1px solid #DC2626;box-shadow:0 1px 2px rgba(15,23,42,.1);',
  secondary:
    'background:var(--cp-surface);color:var(--cp-text);border:1px solid rgba(148,163,184,.4);box-shadow:0 1px 2px rgba(15,23,42,.06);',
  ghost: 'background:transparent;color:var(--cp-muted);border:1px solid transparent;',
};

function parseStyle(css: string): React.CSSProperties {
  const o: Record<string, string> = {};
  css
    .split(';')
    .filter(Boolean)
    .forEach(d => {
      const i = d.indexOf(':');
      if (i > 0) {
        const k = d
          .slice(0, i)
          .trim()
          .replace(/-([a-z])/g, (_, c: string) => c.toUpperCase());
        o[k] = d.slice(i + 1).trim();
      }
    });
  return o as React.CSSProperties;
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  icon?: React.ReactNode;
  iconPosition?: 'left' | 'right';
  loading?: boolean;
}

export default function Button({
  variant = 'primary',
  size = 'md',
  icon,
  iconPosition = 'left',
  loading,
  disabled,
  children,
  style,
  className = '',
  ...rest
}: ButtonProps) {
  const s = sizes[size];
  const iconOnly = !children;
  return (
    <button
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`inline-flex items-center justify-center gap-2 font-medium rounded-lg transition-all duration-200 ease-out hover:-translate-y-px active:translate-y-[1px] disabled:opacity-50 disabled:cursor-not-allowed ${s.pad} ${s.text} ${className}`}
      style={{
        ...parseStyle(fills[variant]),
        ...(iconOnly
          ? {
              padding: size === 'sm' ? '0.5rem' : size === 'lg' ? '0.75rem' : '0.625rem',
              borderRadius: 8,
            }
          : {}),
        ...style,
      }}
      {...rest}
    >
      {loading ? (
        <Loader2 size={s.icon} className="animate-spin" aria-hidden />
      ) : (
        iconPosition === 'left' && icon
      )}
      {children}
      {!loading && iconPosition === 'right' && icon}
    </button>
  );
}
