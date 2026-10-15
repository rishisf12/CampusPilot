import { Loader2 } from 'lucide-react';

interface SpinnerProps {
  size?: number;
  className?: string;
}

export default function Spinner({ size = 20, className = '' }: SpinnerProps) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={`inline-flex items-center justify-center ${className}`}
      style={{
        width: size + 12,
        height: size + 12,
        borderRadius: '50%',
        background: 'var(--cp-surface)',
        boxShadow: 'var(--cp-clay)',
        border: '1px solid rgba(163,177,198,.3)',
      }}
    >
      <Loader2
        size={size}
        strokeWidth={2}
        aria-hidden
        className="animate-spin"
        style={{ color: 'currentColor' }}
      />
    </span>
  );
}
