type Tone = 'success' | 'warning' | 'danger' | 'primary' | 'default';

interface StatusCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  tone?: Tone;
  extra?: React.ReactNode;
}

/**
 * Status display card.
 *
 * `tone` drives the colour: safe/warning/critical map onto the success,
 * warning and danger palettes used across the app.
 */
const TONES: Record<Tone, string> = {
  success: 'border-success-200 bg-success-50 text-success-700',
  warning: 'border-warning-200 bg-warning-50 text-warning-700',
  danger: 'border-danger-200 bg-danger-50 text-danger-700',
  primary: 'border-primary-200 bg-primary-50 text-primary-700',
  default: 'border-gray-200 bg-gray-50 text-gray-700',
};

export default function StatusCard({
  label,
  value,
  subtext,
  tone = 'default',
  extra = null,
}: StatusCardProps) {
  return (
    <div className={`rounded-xl border p-4 ${TONES[tone] || TONES.default}`}>
      <p className="text-xs uppercase tracking-wide opacity-80">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
      {subtext && <p className="text-xs mt-1 opacity-80">{subtext}</p>}
      {extra}
    </div>
  );
}
