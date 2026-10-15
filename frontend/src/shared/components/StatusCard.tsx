import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react';
import { Card, IconTile } from '@/components/ui';

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
const HUES = {
  success: 'mint',
  warning: 'amber',
  danger: 'coral',
  primary: 'indigo',
  default: 'slate',
} as const;

const ICONS = {
  success: CheckCircle2,
  warning: AlertTriangle,
  danger: XCircle,
  primary: Info,
  default: AlertTriangle,
} as const;

export default function StatusCard({
  label,
  value,
  subtext,
  tone = 'default',
  extra = null,
}: StatusCardProps) {
  const Icon = ICONS[tone] || ICONS.default;
  return (
    <Card className="!p-4 flex items-start gap-3">
      <IconTile hue={HUES[tone] || 'slate'} size={40}>
        <Icon size={20} strokeWidth={2} aria-hidden style={{ color: 'currentColor' }} />
      </IconTile>
      <div className="min-w-0 flex-1">
        <p
          className="text-xs font-medium uppercase tracking-wide"
          style={{ color: 'var(--cp-muted)' }}
        >
          {label}
        </p>
        <p className="text-2xl font-bold mt-1" style={{ color: 'var(--cp-text)' }}>
          {value}
        </p>
        {subtext && (
          <p className="text-xs mt-1" style={{ color: 'var(--cp-muted)' }}>
            {subtext}
          </p>
        )}
        {extra}
      </div>
    </Card>
  );
}
