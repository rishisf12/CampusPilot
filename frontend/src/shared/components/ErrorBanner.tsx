import { AlertTriangle, X } from 'lucide-react';
import { Card, IconTile, Button } from '@/components/ui';

interface ErrorBannerProps {
  message: string | null | undefined;
  onDismiss?: () => void;
  className?: string;
}

/** Dismissible banner for API and network errors. */
export default function ErrorBanner({ message, onDismiss, className = '' }: ErrorBannerProps) {
  if (!message) return null;
  return (
    <Card
      role="alert"
      className={`flex items-start gap-3 !p-3 ${className}`}
      style={{ borderColor: 'rgba(239,68,68,.35)' }}
    >
      <IconTile hue="coral" size={32}>
        <AlertTriangle size={18} strokeWidth={2} aria-hidden style={{ color: 'currentColor' }} />
      </IconTile>
      <span className="flex-1 text-sm" style={{ color: 'var(--cp-danger)' }}>
        {message}
      </span>
      {onDismiss && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          icon={<X size={16} strokeWidth={2} aria-hidden style={{ color: 'currentColor' }} />}
          onClick={onDismiss}
          aria-label="Dismiss"
        />
      )}
    </Card>
  );
}
