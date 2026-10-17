import { GraduationCap, ShieldCheck, ArrowRight } from 'lucide-react';
import { Badge, Card } from '@/components/ui';

/**
 * The landing screen: who are you signing in as?
 *
 * Student is the full app; admin is the developer sign-in for feedback
 * responses. Faculty is shown with a "Soon" badge rather than offering a form
 * that would fail.
 *
 * The cards carry a single short line each. An earlier version had a second
 * "detail" sentence on every card ("Track your classes, attendance, exam
 * seating and vacant rooms. Sign in with your password, a passkey, or your
 * college email.") plus a "Choose your role to continue." subtitle and a
 * "Students register with your college email address." footer. Three sentences
 * saying what a label already says, before the user had chosen anything.
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
  /** One short line. The card shows nothing else. */
  description: string;
  available: boolean;
}

const ROLES: Role[] = [
  {
    id: 'student',
    label: 'Student',
    description: 'Timetable, attendance, exams, rooms.',
    available: true,
  },
  {
    id: 'faculty',
    label: 'Faculty',
    description: 'Teaching schedule.',
    available: false,
  },
  {
    id: 'admin',
    label: 'Admin',
    description: 'Feedback responses.',
    available: true,
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
          <h2 className="text-lg font-semibold text-center" style={{ color: 'var(--cp-text)' }}>
            How are you signing in?
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {ROLES.map(role => (
              <RoleCard key={role.id} role={role} onChoose={() => pick(role.id)} />
            ))}
          </div>
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
          {role.description}
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
        {role.description}
      </p>
    </button>
  );
}
