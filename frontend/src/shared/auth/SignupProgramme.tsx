import { ArrowLeft } from 'lucide-react';
import { Badge } from '@/components/ui';
import { GROUP_DETAILS, PROGRAMME_GROUPS, type ProgrammeGroup } from '../constants';
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
 * Each card is now the name of the programme and the degrees that count as it,
 * and nothing else. Every feature list has gone, including the footnote that
 * listed what all three share. None of it answered a question anyone was
 * asking: what you get is the same whichever of the three you pick, so reading
 * it three times was work the screen was asking for and giving nothing back.
 * The nav bar after signup says the same thing far more usefully.
 */
interface SignupProgrammeProps {
  onChoose: (group: ProgrammeGroup) => void;
  onBack: () => void;
}

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
                className="cp-choice cp-choice--primary"
                aria-label={`Join as ${GROUP_DETAILS[group].title}`}
              >
                <span className="block font-semibold" style={{ color: 'var(--cp-text)' }}>
                  {GROUP_DETAILS[group].title}
                </span>
                {/* Which programmes count as this one, set under the name rather
                    than beside it: side by side it fought the title for the same
                    line and squeezed the longer names onto two rows. */}
                <Badge tone="primary" className="mt-1.5">
                  {GROUP_DETAILS[group].programmes}
                </Badge>
              </button>
            ))}
          </div>

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
