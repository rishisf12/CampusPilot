interface ErrorBannerProps {
  message: string | null | undefined;
  onDismiss?: () => void;
  className?: string;
}

/** Dismissible banner for API and network errors. */
export default function ErrorBanner({ message, onDismiss, className = '' }: ErrorBannerProps) {
  if (!message) return null;
  return (
    <div
      role="alert"
      className={`p-3 rounded-lg border border-danger-200 bg-danger-50 text-danger-700 text-sm flex items-start gap-3 ${className}`}
    >
      <svg
        className="w-4 h-4 mt-0.5 shrink-0"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="2"
          d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
      <span className="flex-1">{message}</span>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="text-danger-500 hover:text-danger-700"
          aria-label="Dismiss"
        >
          x
        </button>
      )}
    </div>
  );
}
