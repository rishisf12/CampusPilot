import type { ButtonHTMLAttributes } from 'react';
export default function Toggle({
  checked,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { checked: boolean }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      {...rest}
      className="relative inline-flex items-center rounded-full transition-all duration-200"
      style={{
        width: 52,
        height: 28,
        background: 'var(--cp-bg)',
        boxShadow: 'var(--cp-neu-inset)',
        border: '1px solid rgba(163,177,198,.35)',
      }}
    >
      <span
        aria-hidden
        className="absolute rounded-full transition-all duration-200"
        style={{
          width: 20,
          height: 20,
          left: checked ? 28 : 4,
          background: 'var(--cp-primary)',
          boxShadow: 'var(--cp-neu-raised-sm)',
        }}
      />
    </button>
  );
}
