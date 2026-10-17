import { useMemo, useState, FormEvent, ChangeEvent } from 'react';
import { UserPlus } from 'lucide-react';
import { Button, Card, Input, Select, ProgressBar } from '@/components/ui';
import { authApi } from '../../api';
import {
  BRANCH_OPTIONS,
  GENDERS,
  GROUP_DETAILS,
  GROUP_PROGRAMMES,
  PROGRAMME_BRANCHES,
  PROGRAMME_SEMESTERS,
  semesterLabel,
  type BranchOption,
  type Programme,
  type ProgrammeGroup,
} from '../constants';
import Logo3D from '../../components/layout/Logo3D';

import ErrorBanner from '../components/ErrorBanner';
import SignupProgress from './SignupProgress';

/** YYBBBNNN, e.g. 23BCS125. */
const ROLL_PATTERN = /^\d{2}[A-Z]{3}\d{3}$/;

/** Rough 0-4 password strength. */
function scorePassword(value: string): number {
  let score = 0;
  if (value.length >= 8) score += 1;
  if (value.length >= 12) score += 1;
  if (/[a-z]/.test(value) && /[A-Z]/.test(value)) score += 1;
  if (/\d/.test(value) && /[^A-Za-z0-9]/.test(value)) score += 1;
  return Math.min(score, 4);
}

const STRENGTH_LABELS = ['Too short', 'Weak', 'Fair', 'Good', 'Strong'];

interface SignupFormProps {
  verifiedEmail: string;
  /** Chosen in step 0: narrows the programme and branch lists to one group. */
  programmeGroup: ProgrammeGroup;
  onSwitchToLogin: () => void;
  onRegistered: () => void;
  onStartOver: () => void;
}

/**
 * Registration step 3: the account details.
 *
 * The email is not typed here. It arrives already proven from step 1, and is
 * shown read-only, because the address that owns the account has to be the one
 * that was verified - letting it be edited at this point would let someone prove
 * one mailbox and claim another.
 *
 * The programme group chosen in step 0 shapes this form: only that group's
 * programmes are offered, the branch list follows the programme, and the branch
 * transfer reveal appears only where a transfer can exist - BTech.
 */
export default function SignupForm({
  verifiedEmail,
  programmeGroup,
  onSwitchToLogin,
  onRegistered,
  onStartOver,
}: SignupFormProps) {
  // Start on the first programme of the chosen group, not always BTech.
  const groupProgrammes = GROUP_PROGRAMMES[programmeGroup];
  const firstProgramme = groupProgrammes[0];
  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    gender: 'Male' as const,
    programme: firstProgramme as Programme,
    semester: 1,
    branch: PROGRAMME_BRANCHES[firstProgramme][0] as BranchOption,
    username: '',
    roll_number: '',
    password: '',
    confirm_password: '',
  });
  const [showBranchChange, setShowBranchChange] = useState(false);
  const [branchFrom, setBranchFrom] = useState<string>(PROGRAMME_BRANCHES[firstProgramme][0]);
  const [branchTo, setBranchTo] = useState('');
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const update = (key: string, value: string | number) => {
    setForm(previous => ({ ...previous, [key]: value }));
    setError(null);
  };

  const semesters =
    PROGRAMME_SEMESTERS[form.programme as keyof typeof PROGRAMME_SEMESTERS] ||
    PROGRAMME_SEMESTERS.BTech;

  /** Branches valid for the currently selected programme. */
  const branchOptions: readonly BranchOption[] =
    PROGRAMME_BRANCHES[form.programme as Programme] || BRANCH_OPTIONS;

  /** A transfer only exists inside BTech, so it is offered nowhere else. */
  const canChangeBranch = form.programme === 'BTech';

  const errors = useMemo(() => {
    const found: Record<string, string> = {};
    if (!form.first_name.trim()) found.first_name = 'First name is required';
    if (!form.last_name.trim()) found.last_name = 'Last name is required';
    if (!/^[A-Za-z0-9_.-]{3,30}$/.test(form.username.trim()))
      found.username = '3-30 characters: letters, numbers, dot, dash or underscore';
    const roll = form.roll_number.trim().toUpperCase();
    if (!ROLL_PATTERN.test(roll)) found.roll_number = 'Use YYBBBNNN, e.g. 23BCS125';
    // No email check here: the address was proven in step 1 and is not editable.
    if (form.password.length < 8) found.password = 'At least 8 characters';
    if (form.password !== form.confirm_password) found.confirm_password = 'Passwords do not match';
    if (canChangeBranch && showBranchChange && branchTo && branchTo === branchFrom)
      found.branchTo = 'Choose a different branch';
    return found;
  }, [form, canChangeBranch, showBranchChange, branchFrom, branchTo]);

  const invalid = (key: string) => (touched[key] && errors[key] ? errors[key] : null);
  const strength = scorePassword(form.password);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setTouched({
      first_name: true,
      last_name: true,
      username: true,
      roll_number: true,
      email: true,
      password: true,
      confirm_password: true,
      branchTo: true,
    });
    if (Object.keys(errors).length > 0) {
      setError('Please fix the highlighted fields');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await authApi.signup({
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        gender: form.gender,
        programme: form.programme,
        semester: Number(form.semester),
        // A revealed branch change moves the student to the target branch.
        branch: canChangeBranch && showBranchChange && branchTo ? branchTo : form.branch,
        username: form.username.trim(),
        roll_number: form.roll_number.trim().toUpperCase(),
        // The proven address, not anything typed here.
        email: verifiedEmail,
        password: form.password,
      });
      onRegistered();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center px-4 py-10"
      style={{ background: 'var(--cp-bg)' }}
    >
      <div className="w-full max-w-2xl">
        <div className="text-center mb-6">
          <Logo3D size={24} />
          <h1 className="mt-2 text-2xl font-bold text-primary-500">Create your account</h1>
          <p className="text-xs tracking-widest text-primary-400 font-medium">
            YOUR CAMPUS ASSISTANT
          </p>
        </div>

        <Card className="space-y-4">
          <SignupProgress current="details" />

          <ErrorBanner message={error} onDismiss={() => setError(null)} />

          <form onSubmit={submit} className="space-y-4">
            {/* Names side by side */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label="First name" error={invalid('first_name')}>
                <Input
                  id="su-first"
                  value={form.first_name}
                  onChange={(e: ChangeEvent<HTMLInputElement>) =>
                    update('first_name', e.target.value)
                  }
                  onBlur={() => setTouched(t => ({ ...t, first_name: true }))}
                  required
                />
              </Field>
              <Field label="Last name" error={invalid('last_name')}>
                <Input
                  id="su-last"
                  value={form.last_name}
                  onChange={(e: ChangeEvent<HTMLInputElement>) =>
                    update('last_name', e.target.value)
                  }
                  onBlur={() => setTouched(t => ({ ...t, last_name: true }))}
                  required
                />
              </Field>
            </div>

            {/* Gender + programme */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label="Gender">
                <Select
                  id="su-gender"
                  value={form.gender}
                  onChange={(e: ChangeEvent<HTMLSelectElement>) => update('gender', e.target.value)}
                >
                  {GENDERS.map(gender => (
                    <option key={gender} value={gender}>
                      {gender}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field
                label="Programme"
                hint={
                  groupProgrammes.length > 1
                    ? `${GROUP_DETAILS[programmeGroup].title} programmes only.`
                    : undefined
                }
              >
                <Select
                  id="su-programme"
                  value={form.programme}
                  onChange={(e: ChangeEvent<HTMLSelectElement>) => {
                    const programme = e.target.value as Programme;
                    const options =
                      PROGRAMME_SEMESTERS[programme as keyof typeof PROGRAMME_SEMESTERS] || [];
                    update('programme', programme);
                    const nextSemester = (options as readonly number[]).includes(
                      Number(form.semester)
                    )
                      ? form.semester
                      : options[0];
                    update('semester', nextSemester as string | number);
                    // The branch list belongs to the programme, so a programme
                    // change re-picks the first valid branch rather than
                    // silently keeping one from another programme.
                    const branches = PROGRAMME_BRANCHES[programme] || BRANCH_OPTIONS;
                    const nextBranch = branches.includes(form.branch as BranchOption)
                      ? form.branch
                      : branches[0];
                    update('branch', nextBranch);
                    setBranchFrom(nextBranch);
                    setBranchTo('');
                    setShowBranchChange(false);
                  }}
                >
                  {groupProgrammes.map(programme => (
                    <option key={programme} value={programme}>
                      {programme}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>

            {/* Semester + branch */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label="Semester">
                <Select
                  id="su-semester"
                  value={form.semester}
                  onChange={(e: ChangeEvent<HTMLSelectElement>) =>
                    update('semester', e.target.value)
                  }
                >
                  {semesters.map(value => (
                    <option key={value} value={value}>
                      {semesterLabel(value)}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field
                label="Branch"
                hint={branchOptions.length === 1 ? 'Fixed for this programme.' : undefined}
              >
                <Select
                  id="su-branch"
                  value={form.branch}
                  onChange={(e: ChangeEvent<HTMLSelectElement>) => {
                    update('branch', e.target.value);
                    setBranchFrom(e.target.value);
                  }}
                >
                  {branchOptions.map(branch => (
                    <option key={branch} value={branch}>
                      {branch}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>

            {/* Branch change reveal - a BTech transfer only, so hidden elsewhere. */}
            {canChangeBranch && (
              <div className="neu-inset p-3 rounded-xl">
                <div className="flex flex-wrap items-center gap-3">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => setShowBranchChange(value => !value)}
                  >
                    {showBranchChange ? 'Hide branch change' : 'Branch changed'}
                  </Button>
                  <span className="text-xs" style={{ color: 'var(--cp-muted)' }}>
                    Already applied for a branch transfer? Add it now.
                  </span>
                </div>

                {showBranchChange && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
                    <Field label="From branch">
                      <Select
                        id="su-branch-from"
                        value={branchFrom}
                        onChange={(e: ChangeEvent<HTMLSelectElement>) =>
                          setBranchFrom(e.target.value)
                        }
                      >
                        <option value="">Select branch</option>
                        {BRANCH_OPTIONS.map(branch => (
                          <option key={branch} value={branch}>
                            {branch}
                          </option>
                        ))}
                      </Select>
                    </Field>
                    <Field label="To branch" error={invalid('branchTo')}>
                      <Select
                        id="su-branch-to"
                        value={branchTo}
                        onChange={(e: ChangeEvent<HTMLSelectElement>) => {
                          setBranchTo(e.target.value);
                          setTouched(t => ({ ...t, branchTo: true }));
                        }}
                      >
                        <option value="">Select branch</option>
                        {BRANCH_OPTIONS.map(branch => (
                          <option key={branch} value={branch}>
                            {branch}
                          </option>
                        ))}
                      </Select>
                    </Field>
                  </div>
                )}
              </div>
            )}

            {/* Username + roll */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label="Username" error={invalid('username')}>
                <Input
                  id="su-username"
                  value={form.username}
                  onChange={(e: ChangeEvent<HTMLInputElement>) =>
                    update('username', e.target.value.replace(/\s/g, ''))
                  }
                  onBlur={() => setTouched(t => ({ ...t, username: true }))}
                  autoComplete="username"
                  required
                />
              </Field>
              <Field label="Roll number" error={invalid('roll_number')}>
                <Input
                  id="su-roll"
                  className="font-mono uppercase"
                  value={form.roll_number}
                  onChange={(e: ChangeEvent<HTMLInputElement>) =>
                    update(
                      'roll_number',
                      e.target.value
                        .toUpperCase()
                        .replace(/[^A-Z0-9]/g, '')
                        .slice(0, 8)
                    )
                  }
                  onBlur={() => setTouched(t => ({ ...t, roll_number: true }))}
                  placeholder="23BCS125"
                  maxLength={8}
                  required
                />
              </Field>
            </div>

            {/* Already verified in step 1, so shown but not editable. */}
            <Field label="College email" hint="Verified in the previous step.">
              <Input
                id="su-email"
                type="email"
                value={verifiedEmail}
                readOnly
                aria-readonly="true"
                style={{ color: 'var(--cp-muted)' }}
              />
              <button
                type="button"
                onClick={onStartOver}
                className="mt-1 text-xs text-primary-600 hover:underline"
              >
                Use a different email
              </button>
            </Field>

            {/* Password + strength */}
            <Field label="Password" error={invalid('password')}>
              <Input
                id="su-password"
                type="password"
                value={form.password}
                onChange={(e: ChangeEvent<HTMLInputElement>) => update('password', e.target.value)}
                onBlur={() => setTouched(t => ({ ...t, password: true }))}
                autoComplete="new-password"
                required
              />
              {form.password && (
                <div className="mt-2">
                  <ProgressBar
                    value={strength}
                    max={4}
                    label={`Password strength: ${STRENGTH_LABELS[strength]}`}
                  />
                </div>
              )}
            </Field>

            <Field label="Confirm password" error={invalid('confirm_password')}>
              <Input
                id="su-confirm"
                type="password"
                value={form.confirm_password}
                onChange={(e: ChangeEvent<HTMLInputElement>) =>
                  update('confirm_password', e.target.value)
                }
                onBlur={() => setTouched(t => ({ ...t, confirm_password: true }))}
                autoComplete="new-password"
                required
              />
            </Field>

            <Button
              type="submit"
              variant="primary"
              icon={<UserPlus size={18} />}
              loading={loading}
              className="w-full"
            >
              Create account
            </Button>
          </form>

          <p className="text-sm text-center" style={{ color: 'var(--cp-muted)' }}>
            Already registered?{' '}
            <button
              type="button"
              onClick={onSwitchToLogin}
              className="font-medium text-primary-600 hover:underline"
            >
              Sign in
            </button>
          </p>
        </Card>
      </div>
    </div>
  );
}

/** Label + control + inline error/hint. */
interface FieldProps {
  label: string;
  error?: string | null;
  hint?: string;
  children: React.ReactNode;
}

function Field({ label, error, hint, children }: FieldProps) {
  return (
    <div>
      <span className="label">{label}</span>
      {children}
      {error ? (
        <p className="text-xs text-danger-600 mt-1">{error}</p>
      ) : hint ? (
        <p className="text-xs mt-1" style={{ color: 'var(--cp-muted)' }}>
          {hint}
        </p>
      ) : null}
    </div>
  );
}
