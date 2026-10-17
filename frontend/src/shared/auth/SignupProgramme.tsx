import { ArrowLeft } from 'lucide-react';
import { Badge } from '@/components/ui';
import {
  GROUP_CLASSROOM_TABS,
  GROUP_DETAILS,
  NAV_TABS,
  PROGRAMME_GROUPS,
  type ProgrammeGroup,
} from '../constants';
import SignupProgress from './SignupProgress';
import TechBackground from './TechBackground';
import Logo3D from '../../components/layout/Logo3D';

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
 *
 * The three options sit side by side rather than stacked. Stacked, each card
 * carried a sentence of prose and a row of feature chips, and the whole thing
 * ran off the bottom of a phone screen - so the third option, Doctoral, was
 * only reachable by scrolling, and a choice that is really a comparison is
 * easiest to make when all three are visible at once.
 *
 * The prose is gone for the same reason. "We shape the app around your answer"
 * and "Classes, attendance, exams, rooms and teams - the full campus toolkit"
 * both restate what the three cards already show: the chips *are* the feature
 * list, so the sentence above them was a second, wordier copy of it.
 *
 * Only the chips that differ per programme stay on the cards. Team, Feedback
 * and Profile are on all three, so they are stated once underneath instead.
 */
interface SignupProgrammeProps {
  onChoose: (group: ProgrammeGroup) => void;
  onBack: () => void;
}

/** Sections everyone gets, whatever the group. */
const COMMON_SECTIONS = ['My Team', 'Feedback', 'Profile'];

export default function SignupProgramme({ onChoose, onBack }: SignupProgrammeProps) {
  return (
    <div className="cp-auth-root min-h-screen flex items-center justify-center px-4 py-8">
      <TechBackground />

      <div className="relative w-full max-w-3xl">
        <div className="text-center mb-5">
          <Logo3D size={32} />
          <h1 className="mt-2 text-2xl font-bold text-primary-500">essential</h1>
          <p className="cp-tagline mt-1">YOUR CAMPUS ASSISTANT</p>
        </div>

        <div className="cp-card">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <h2 className="cp-card-title !mb-0">Which programme are you in?</h2>
            <SignupProgress current="programme" />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {PROGRAMME_GROUPS.map(group => (
              <button
                key={group}
                type="button"
                onClick={() => onChoose(group)}
                className="cp-choice"
                aria-label={`Join as ${GROUP_DETAILS[group].title}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold" style={{ color: 'var(--cp-text)' }}>
                    {GROUP_DETAILS[group].title}
                  </span>
                  <Badge tone="primary">{GROUP_DETAILS[group].programmes}</Badge>
                </div>
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {classroomLabels(group).map(label => (
                    <Badge key={label} tone="neutral">
                      {label}
                    </Badge>
                  ))}
                </div>
              </button>
            ))}
          </div>

          {/* Stated once, not repeated on all three cards.
              Team, Feedback and Profile are on every programme, so printing
              them inside each card spent nine chips saying one thing - and on a
              phone that alone was the difference between fitting and scrolling. */}
          <p className="text-xs text-center mt-3" style={{ color: 'var(--cp-muted)' }}>
            Every programme also includes {COMMON_SECTIONS.join(', ').toLowerCase()}.
          </p>

          <div className="mt-4 pt-3 text-center flex flex-wrap items-center justify-center gap-3">
            <span className="text-sm" style={{ color: 'var(--cp-muted)' }}>
              Already registered?{' '}
              <button type="button" onClick={onBack} className="cp-link">
                Sign in
              </button>
            </span>
            <button type="button" onClick={onBack} className="cp-backlink">
              <ArrowLeft size={14} aria-hidden />
              Back
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/** The classroom features this group will see, as labels for the preview chips. */
function classroomLabels(group: ProgrammeGroup): string[] {
  const allowed = GROUP_CLASSROOM_TABS[group];
  return NAV_TABS.filter(tab => allowed.includes(tab.id)).map(tab => tab.label);
}
