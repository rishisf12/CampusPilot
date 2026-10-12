/**
 * The registration step ladder, shared by every signup screen.
 *
 * Programme -> Email -> Code -> Details. The programme choice comes first
 * because it shapes everything after it: which programmes the details step
 * offers, and which features wait on the other side of the finished signup.
 * One component keeps the three screens agreeing on labels and numbering -
 * previously the ladder lived inside the email screen and the details screen
 * had none at all.
 */

export type SignupStage = 'programme' | 'email' | 'code' | 'details';

const ORDER: SignupStage[] = ['programme', 'email', 'code', 'details'];

const LABELS: Record<SignupStage, string> = {
  programme: 'Programme',
  email: 'Email',
  code: 'Code',
  details: 'Details',
};

export default function SignupProgress({ current }: { current: SignupStage }) {
  const activeIndex = ORDER.indexOf(current);
  return (
    <ol className="flex items-center gap-2 text-xs">
      {ORDER.map((stage, index) => (
        <Step
          key={stage}
          n={index + 1}
          label={LABELS[stage]}
          done={index < activeIndex}
          active={index === activeIndex}
          last={index === ORDER.length - 1}
        />
      ))}
    </ol>
  );
}

interface StepProps {
  n: number;
  label: string;
  done: boolean;
  active: boolean;
  last: boolean;
}

/** One step in the ladder: a filled dot for done, a highlighted one for current. */
function Step({ n, label, done, active, last }: StepProps) {
  return (
    <li
      className={`flex items-center gap-2 ${active ? 'text-primary-600' : done ? 'text-success-600' : 'text-gray-400'}`}
    >
      <span className="flex items-center gap-1.5">
        <span
          className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-semibold ${
            done
              ? 'bg-success-500 text-white'
              : active
                ? 'bg-primary-500 text-white'
                : 'bg-gray-200 text-gray-500'
          }`}
        >
          {done ? '✓' : n}
        </span>
        <span className="hidden sm:inline">{label}</span>
      </span>
      {!last && <span className="flex-1 h-px bg-gray-200 min-w-4" aria-hidden="true" />}
    </li>
  );
}
