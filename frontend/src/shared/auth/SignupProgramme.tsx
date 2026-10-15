import { ArrowLeft } from 'lucide-react';
import { Badge, Button, Card } from '@/components/ui';
import {
  GROUP_CLASSROOM_TABS,
  GROUP_DETAILS,
  NAV_TABS,
  PROGRAMME_GROUPS,
  type ProgrammeGroup,
} from '../constants';
import SignupProgress from './SignupProgress';

/**
 * Registration step 0: which programme are you here for?
 *
 * Asked before the email, not after, because the answer is not just a field on
 * the profile - it decides which features exist on the other side of signup.
 * An undergraduate gets the full classroom toolkit; a master's student gets
 * classes and exams without the UG machinery; a doctoral scholar gets the
 * lightest bundle of all. Nothing is created by this screen, so abandoning it
 * costs nothing - the choice simply travels in wrapper state to the details
 * step, where it pre-filters the programme list.
 */
interface SignupProgrammeProps {
  onChoose: (group: ProgrammeGroup) => void;
  onBack: () => void;
}

/** Sections everyone gets, whatever the group. */
const COMMON_SECTIONS = ['My Team', 'Feedback', 'Profile'];

export default function SignupProgramme({ onChoose, onBack }: SignupProgrammeProps) {
  return (
    <div
      className="min-h-screen flex items-center justify-center px-4 py-12"
      style={{ background: 'var(--cp-bg)' }}
    >
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <img src="/logo-icon.svg" alt="Essential" className="w-16 h-16 mx-auto" />
          <h1 className="mt-3 text-2xl font-bold text-primary-500">essential</h1>
          <p className="text-xs tracking-widest text-primary-400 font-medium">
            YOUR CAMPUS ASSISTANT
          </p>
        </div>

        <Card className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold" style={{ color: 'var(--cp-text)' }}>
              Which programme are you in?
            </h2>
            <p className="text-sm mt-1" style={{ color: 'var(--cp-muted)' }}>
              We shape the app around your answer - your classes, your exams, nothing extra in the
              way.
            </p>
          </div>

          <SignupProgress current="programme" />

          <div className="space-y-3">
            {PROGRAMME_GROUPS.map(group => (
              <button
                key={group}
                type="button"
                onClick={() => onChoose(group)}
                className="neu-raised w-full text-left p-4 rounded-xl hover:-translate-y-px transition-all"
                aria-label={`Join as ${GROUP_DETAILS[group].title}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold" style={{ color: 'var(--cp-text)' }}>
                    {GROUP_DETAILS[group].title}
                  </span>
                  <Badge tone="primary">{GROUP_DETAILS[group].programmes}</Badge>
                </div>
                <p className="text-sm mt-1" style={{ color: 'var(--cp-muted)' }}>
                  {GROUP_DETAILS[group].blurb}
                </p>
                <div className="flex flex-wrap gap-1.5 mt-2.5">
                  {[...classroomLabels(group), ...COMMON_SECTIONS].map(label => (
                    <Badge key={label} tone="neutral">
                      {label}
                    </Badge>
                  ))}
                </div>
              </button>
            ))}
          </div>

          <div
            className="border-t pt-3 text-center"
            style={{ borderColor: 'rgba(163,177,198,.3)' }}
          >
            <p className="text-sm" style={{ color: 'var(--cp-muted)' }}>
              Already registered?{' '}
              <button
                type="button"
                onClick={onBack}
                className="font-medium text-primary-600 hover:underline"
              >
                Sign in
              </button>
            </p>
            <p className="text-center mt-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                icon={<ArrowLeft size={14} />}
                onClick={onBack}
              >
                Back
              </Button>
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
}

/** The classroom features this group will see, as labels for the preview chips. */
function classroomLabels(group: ProgrammeGroup): string[] {
  const allowed = GROUP_CLASSROOM_TABS[group];
  return NAV_TABS.filter(tab => allowed.includes(tab.id)).map(tab => tab.label);
}
