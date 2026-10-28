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

export default function SignupProgress({
  current,
  faculty = false,
}: {
  current: SignupStage;
  /** Faculty signup skips the programme step: Email -> Code -> Details. */
  faculty?: boolean;
}) {
  const steps: SignupStage[] = faculty ? ORDER.filter(stage => stage !== 'programme') : ORDER;
  const activeIndex = steps.indexOf(current);
  return (
    <ol className="flex items-center gap-2 text-xs" aria-label="Signup progress">
      {steps.map((stage, index) => (
        <Step
          key={stage}
          n={index + 1}
          label={LABELS[stage]}
          done={index < activeIndex}
          active={index === activeIndex}
          last={index === steps.length - 1}
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
      aria-current={active ? 'step' : undefined}
      className="flex items-center gap-2"
      style={{ color: active ? 'var(--cp-text)' : done ? '#047857' : 'var(--cp-muted)' }}
    >
      <span className="flex items-center gap-1.5">
        <span
          className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-semibold"
          style={
            done
              ? {
                  background: 'var(--cp-primary)',
                  color: 'var(--cp-on-primary)',
                  boxShadow: 'var(--cp-clay)',
                }
              : active
                ? {
                    background: 'var(--cp-primary)',
                    color: 'var(--cp-on-primary)',
                    boxShadow: 'var(--cp-clay)',
                  }
                : {
                    background: 'var(--cp-bg)',
                    color: 'var(--cp-muted)',
                    boxShadow: 'var(--cp-neu-inset)',
                  }
          }
        >
          {n}
        </span>
        <span className="hidden sm:inline">{label}</span>
      </span>
      {!last && (
        <span
          className="flex-1 h-px min-w-4"
          style={{ background: 'rgba(163,177,198,.4)' }}
          aria-hidden="true"
        />
      )}
    </li>
  );
}
