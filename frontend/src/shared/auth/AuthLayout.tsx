import { ArrowLeft } from 'lucide-react';
import type { ReactNode } from 'react';

import AnimatedLogo from './AnimatedLogo';
import AnimatedTitle from './AnimatedTitle';
import TechBackground from './TechBackground';

/**
 * The frame every auth page shares: background, lockup, optional back link,
 * micro-label, then the card.
 *
 * This exists so the sign-in, sign-up and admin pages cannot drift apart from
 * the role picker. Each one supplies only its own content; the arrangement
 * around it lives here.
 *
 * `children` is the card. It is rendered as-is rather than wrapped in a <Card>,
 * because the forms already bring their own and nesting two card surfaces would
 * give a double border and a doubled shadow.
 */
interface AuthLayoutProps {
  /** Small monospace line above the card title, e.g. "// STUDENT ACCESS". */
  microLabel?: string;
  /** Title inside the card. */
  title?: string;
  /** Renders the back link when provided. */
  onBack?: () => void;
  /** Shrinks the lockup so a tall form keeps the focus. */
  scale?: number;
  children: ReactNode;
}

export default function AuthLayout({
  microLabel,
  title,
  onBack,
  scale = 0.85,
  children,
}: AuthLayoutProps) {
  return (
    <div className="cp-auth-root min-h-screen flex items-center justify-center px-4 py-10">
      <TechBackground />

      <div className="relative w-full max-w-md">
        <div className="cp-lockup mb-6">
          <AnimatedLogo size={52} />
          <div className="mt-2">
            <AnimatedTitle scale={scale} />
          </div>
        </div>

        {onBack && (
          <div className="mb-3">
            <button type="button" onClick={onBack} className="cp-backlink">
              <ArrowLeft size={14} aria-hidden />
              Back
            </button>
          </div>
        )}

        <div className="cp-card">
          {microLabel && <p className="cp-microlabel">{microLabel}</p>}
          {title && <h2 className="cp-card-title">{title}</h2>}
          {children}
        </div>
      </div>
    </div>
  );
}
