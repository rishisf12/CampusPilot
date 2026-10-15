export default function ProgressBar({
  value,
  max = 100,
  label,
}: {
  value: number;
  max?: number;
  label?: string;
}) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div>
      {label && (
        <div className="text-sm mb-1" style={{ color: 'var(--cp-muted)' }}>
          {label} — {Math.round(pct)}%
        </div>
      )}
      <div
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label ?? 'progress'}
        className="w-full h-3 overflow-hidden"
        style={{ borderRadius: 6, background: 'var(--cp-bg)', boxShadow: 'var(--cp-neu-inset)' }}
      >
        <div
          className="h-full transition-all duration-200"
          style={{
            width: `${pct}%`,
            borderRadius: 6,
            background: 'var(--cp-primary)',
            boxShadow: 'inset 1px 1px 2px rgba(255,255,255,.4)',
          }}
        />
      </div>
    </div>
  );
}
