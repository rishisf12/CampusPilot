import {
  GROUP_CLASSROOM_TABS,
  GROUP_DETAILS,
  NAV_TABS,
  PROGRAMME_GROUPS,
  type ProgrammeGroup,
} from '../../../shared/constants';
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
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <img src="/logo-icon.svg" alt="Essential" className="w-16 h-16 mx-auto" />
          <h1 className="mt-3 text-2xl font-bold text-primary-500">essential</h1>
          <p className="text-xs tracking-widest text-primary-400 font-medium">
            YOUR CAMPUS ASSISTANT
          </p>
        </div>

        <div className="card space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Which programme are you in?</h2>
            <p className="text-sm text-gray-600 mt-1">
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
                className="w-full text-left p-4 rounded-xl border border-gray-200 bg-white hover:border-primary-300 hover:bg-primary-50 transition-colors group"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-gray-900">{GROUP_DETAILS[group].title}</span>
                  <span className="text-xs font-medium text-primary-600 bg-primary-50 rounded-full px-2 py-0.5">
                    {GROUP_DETAILS[group].programmes}
                  </span>
                </div>
                <p className="text-sm text-gray-600 mt-1">{GROUP_DETAILS[group].blurb}</p>
                <div className="flex flex-wrap gap-1.5 mt-2.5">
                  {[...classroomLabels(group), ...COMMON_SECTIONS].map(label => (
                    <span
                      key={label}
                      className="text-[11px] text-gray-600 bg-gray-100 rounded-full px-2 py-0.5"
                    >
                      {label}
                    </span>
                  ))}
                </div>
              </button>
            ))}
          </div>

          <div className="border-t border-gray-200 pt-3 text-center">
            <p className="text-sm text-gray-600">
              Already registered?{' '}
              <button
                type="button"
                onClick={onBack}
                className="font-medium text-primary-600 hover:underline"
              >
                Sign in
              </button>
            </p>
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
