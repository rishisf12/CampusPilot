import { GraduationCap, ShieldCheck, ArrowRight } from 'lucide-react';
import { Badge, Card } from '@/components/ui';

/**
 * The landing screen: who are you signing in as?
 *
 * Student is the full app; admin is the developer sign-in for feedback
 * responses. Faculty is shown so the shape of the product is visible, but it
 * says plainly that it is not built yet rather than offering a form that
 * would fail.
 *
 * Two choices were made here on purpose:
 *
 * - **Nothing is stored.** The choice is not persisted, so no new localStorage
 *   key is introduced for what is only a routing decision. Picking a role again
 *   costs one click.
 * - **No role is claimed by picking.** The account's own role decides what
 *   opens; picking admin with a student account signs straight back out.
 */
interface Role {
  id: string;
  label: string;
  description: string;
  available: boolean;
  detail: string;
}

const ROLES: Role[] = [
  {
    id: 'student',
    label: 'Student',
    description: 'Your timetable, attendance, exam hall and seats.',
    available: true,
    detail:
      'Track your classes, attendance, exam seating and vacant rooms. Sign in with your password, a passkey, or your college email.',
  },
  {
    id: 'faculty',
    label: 'Faculty',
    description: 'Teaching schedule and your classes.',
    available: false,
    detail: 'Not built yet. Faculty accounts are on the way.',
  },
  {
    id: 'admin',
    label: 'Admin',
    description: 'Feedback responses and publishing.',
    available: true,
    detail: 'Developer sign-in to answer student feedback.',
  },
];

interface StartScreenProps {
  onChooseStudent?: () => void;
  onChooseAdmin?: () => void;
}

export default function StartScreen({ onChooseStudent, onChooseAdmin }: StartScreenProps) {
  const pick = (id: string) => {
    if (id === 'admin') onChooseAdmin?.();
    else onChooseStudent?.();
  };
  return (
    <div
      className="min-h-screen flex items-center justify-center px-4 py-12"
      style={{ background: 'var(--cp-bg)' }}
    >
      <div className="w-full max-w-2xl">
        <div className="text-center mb-8">
          <img src="/logo-icon.svg" alt="Essential" className="w-16 h-16 mx-auto" />
          <h1 className="mt-3 text-2xl font-bold text-primary-500">essential</h1>
          <p className="text-xs tracking-widest text-primary-400 font-medium">
            YOUR CAMPUS ASSISTANT
          </p>
        </div>

        <Card className="space-y-5">
          <div className="text-center">
            <h2 className="text-lg font-semibold" style={{ color: 'var(--cp-text)' }}>
              How are you signing in?
            </h2>
            <p className="text-sm mt-1" style={{ color: 'var(--cp-muted)' }}>
              Choose your role to continue.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {ROLES.map(role => (
              <RoleCard key={role.id} role={role} onChoose={() => pick(role.id)} />
            ))}
          </div>

          <p className="text-xs text-center pt-1" style={{ color: 'var(--cp-muted)' }}>
            Students register with your college email address.
          </p>
        </Card>
      </div>
    </div>
  );
}

function RoleCard({ role, onChoose }: { role: Role; onChoose: () => void }) {
  const Icon = role.id === 'admin' ? ShieldCheck : GraduationCap;
  if (!role.available) {
    return (
      <div
        className="neu-inset rounded-xl p-4 text-left"
        // Not a control: there is nothing to click, so it is not a button.
        aria-disabled="true"
      >
        <div className="flex items-center justify-between gap-2">
          <span
            className="font-semibold flex items-center gap-1.5"
            style={{ color: 'var(--cp-muted)' }}
          >
            <Icon size={18} aria-hidden /> {role.label}
          </span>
          <Badge tone="neutral">Soon</Badge>
        </div>
        <p className="text-xs mt-1.5" style={{ color: 'var(--cp-muted)' }}>
          {role.detail}
        </p>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={onChoose}
      aria-label={`Continue as ${role.label}`}
      className="neu-raised rounded-xl p-4 text-left hover:-translate-y-px focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2 transition-all"
    >
      <div className="flex items-center justify-between gap-2">
        <span
          className="font-semibold flex items-center gap-1.5"
          style={{ color: 'var(--cp-text)' }}
        >
          <Icon size={18} aria-hidden /> {role.label}
        </span>
        <span aria-hidden="true" className="text-primary-500">
          <ArrowRight size={18} />
        </span>
      </div>
      <p className="text-xs mt-1.5" style={{ color: 'var(--cp-muted)' }}>
        {role.detail}
      </p>
    </button>
  );
}
