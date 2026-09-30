export default function ErrorBanner({ message, onDismiss }) {
  if (!message) return null

  return (
    <div className="mb-4 p-4 bg-danger-100 border border-danger-500 text-danger-700 rounded-lg flex items-center justify-between animate-slide-down" role="alert">
      <div className="flex items-center gap-2">
        <svg className="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
        </svg>
        <span className="text-sm font-medium">{message}</span>
      </div>
      <button
        onClick={onDismiss}
        className="text-danger-500 hover:text-danger-700 font-bold text-lg leading-none px-2"
        aria-label="Dismiss error"
      >
        ×
      </button>
    </div>
  )
}