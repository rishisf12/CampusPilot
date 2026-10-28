import { X } from 'lucide-react';
import { useEffect } from 'react';
export default function Modal({
  title,
  onClose,
  children,
  sheet = false,
  wide = false,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  /**
   * Bottom-sheet on phones, centered dialog on sm+ screens. Opt-in so the
   * existing centered usages (passkeys, attendance) are untouched.
   */
  sheet?: boolean;
  /** Wide dialog (max-w-4xl) for side-by-side content like the uploads row. */
  wide?: boolean;
}) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [onClose]);
  return (
    <div
      className={`fixed inset-0 z-50 flex p-4 ${sheet ? 'items-end justify-center p-0 sm:items-center sm:justify-center sm:p-4' : 'items-center justify-center'}`}
      style={{ background: 'rgba(27,31,42,.45)', backdropFilter: 'blur(4px)' }}
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`neu-raised w-full p-6 ${sheet ? 'max-w-lg rounded-b-none animate-slide-down sm:rounded-[1rem]' : wide ? 'max-w-4xl' : 'max-w-lg'}`}
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button
            aria-label="Close dialog"
            onClick={onClose}
            className="neu-raised-sm p-2 rounded-xl"
          >
            <X size={18} aria-hidden />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
