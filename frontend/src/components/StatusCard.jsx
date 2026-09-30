export default function StatusCard({ label, value, status, subtext }) {
  const statusConfig = {
    Safe: { bg: 'bg-success-100', text: 'text-success-700', border: 'border-success-500', dot: 'bg-success-500' },
    Warning: { bg: 'bg-warning-100', text: 'text-warning-700', border: 'border-warning-500', dot: 'bg-warning-500' },
    Critical: { bg: 'bg-danger-100', text: 'text-danger-700', border: 'border-danger-500', dot: 'bg-danger-500' },
    default: { bg: 'bg-gray-100', text: 'text-gray-700', border: 'border-gray-400', dot: 'bg-gray-400' },
  }

  const config = statusConfig[status] || statusConfig.default

  return (
    <div className={`p-4 rounded-xl border-2 ${config.border} ${config.bg} ${config.text} transition-all hover:shadow-md`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500 uppercase tracking-wide">{label}</p>
          <p className="text-3xl font-bold mt-1">{value}</p>
          {subtext && <p className="text-xs mt-1 opacity-80">{subtext}</p>}
        </div>
        <div className={`w-3 h-3 rounded-full ${config.dot} animate-pulse`} aria-hidden="true" />
      </div>
    </div>
  )
}