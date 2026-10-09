import { useMemo, useState, FormEvent, ChangeEvent } from 'react';
import { authApi } from '../api';
import {
  BRANCH_OPTIONS,
  GENDERS,
  PROGRAMMES,
  PROGRAMME_SEMESTERS,
  semesterLabel,
} from '../constants';
import ErrorBanner from './ErrorBanner';
import Spinner from './Spinner';

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
const STRENGTH_BARS = [
  'bg-danger-500',
  'bg-danger-500',
  'bg-warning-500',
  'bg-success-500',
  'bg-success-500',
];

interface SignupFormProps {
  verifiedEmail: string;
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
 */
export default function SignupForm({
  verifiedEmail,
  onSwitchToLogin,
  onRegistered,
  onStartOver,
}: SignupFormProps) {
  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    gender: 'Male' as const,
    programme: 'BTech' as const,
    semester: 1,
    branch: 'CSE A',
    username: '',
    roll_number: '',
    password: '',
    confirm_password: '',
  });
  const [showBranchChange, setShowBranchChange] = useState(false);
  const [branchFrom, setBranchFrom] = useState('CSE A');
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
    if (showBranchChange && branchTo && branchTo === branchFrom)
      found.branchTo = 'Choose a different branch';
    return found;
  }, [form, showBranchChange, branchFrom, branchTo]);

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
        branch: showBranchChange && branchTo ? branchTo : form.branch,
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
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-2xl">
        <div className="text-center mb-6">
          <img src="/logo-icon.svg" alt="Essential" className="w-14 h-14 mx-auto" />
          <h1 className="mt-2 text-2xl font-bold text-primary-500">Create your account</h1>
          <p className="text-xs tracking-widest text-primary-400 font-medium">
            YOUR CAMPUS ASSISTANT
          </p>
        </div>

        <div className="card space-y-4">
          <ErrorBanner message={error} onDismiss={() => setError(null)} />

          <form onSubmit={submit} className="space-y-4">
            {/* Names side by side */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label="First name" error={invalid('first_name')}>
                <input
                  id="su-first"
                  className="input-field"
                  value={form.first_name}
                  onChange={(e: ChangeEvent<HTMLInputElement>) =>
                    update('first_name', e.target.value)
                  }
                  onBlur={() => setTouched(t => ({ ...t, first_name: true }))}
                  required
                />
              </Field>
              <Field label="Last name" error={invalid('last_name')}>
                <input
                  id="su-last"
                  className="input-field"
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
                <select
                  id="su-gender"
                  className="select-field"
                  value={form.gender}
                  onChange={(e: ChangeEvent<HTMLSelectElement>) => update('gender', e.target.value)}
                >
                  {GENDERS.map(gender => (
                    <option key={gender} value={gender}>
                      {gender}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Programme">
                <select
                  id="su-programme"
                  className="select-field"
                  value={form.programme}
                  onChange={(e: ChangeEvent<HTMLSelectElement>) => {
                    const programme = e.target.value;
                    const options =
                      PROGRAMME_SEMESTERS[programme as keyof typeof PROGRAMME_SEMESTERS] || [];
                    update('programme', programme);
                    const nextSemester = (options as readonly number[]).includes(
                      Number(form.semester)
                    )
                      ? form.semester
                      : options[0];
                    update('semester', nextSemester as string | number);
                  }}
                >
                  {PROGRAMMES.map(programme => (
                    <option key={programme} value={programme}>
                      {programme}
                    </option>
                  ))}
                </select>
              </Field>
            </div>

            {/* Semester + branch */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label="Semester">
                <select
                  id="su-semester"
                  className="select-field"
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
                </select>
              </Field>
              <Field label="Branch">
                <select
                  id="su-branch"
                  className="select-field"
                  value={form.branch}
                  onChange={(e: ChangeEvent<HTMLSelectElement>) => {
                    update('branch', e.target.value);
                    setBranchFrom(e.target.value);
                  }}
                >
                  {BRANCH_OPTIONS.map(branch => (
                    <option key={branch} value={branch}>
                      {branch}
                    </option>
                  ))}
                </select>
              </Field>
            </div>

            {/* Branch change reveal */}
            <div className="p-3 rounded-lg border border-gray-200 bg-gray-50">
              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={() => setShowBranchChange(value => !value)}
                  className="btn-secondary text-sm"
                >
                  {showBranchChange ? 'Hide branch change' : 'Branch changed'}
                </button>
                <span className="text-xs text-gray-600">
                  Already applied for a branch transfer? Add it now.
                </span>
              </div>

              {showBranchChange && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
                  <Field label="From branch">
                    <select
                      id="su-branch-from"
                      className="select-field"
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
                    </select>
                  </Field>
                  <Field label="To branch" error={invalid('branchTo')}>
                    <select
                      id="su-branch-to"
                      className="select-field"
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
                    </select>
                  </Field>
                </div>
              )}
            </div>

            {/* Username + roll */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label="Username" error={invalid('username')}>
                <input
                  id="su-username"
                  className="input-field"
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
                <input
                  id="su-roll"
                  className="input-field font-mono uppercase"
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
              <input
                id="su-email"
                type="email"
                className="input-field bg-gray-50 text-gray-600"
                value={verifiedEmail}
                readOnly
                aria-readonly="true"
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
              <input
                id="su-password"
                type="password"
                className="input-field"
                value={form.password}
                onChange={(e: ChangeEvent<HTMLInputElement>) => update('password', e.target.value)}
                onBlur={() => setTouched(t => ({ ...t, password: true }))}
                autoComplete="new-password"
                required
              />
              {form.password && (
                <div className="mt-2">
                  <div className="flex gap-1">
                    {[0, 1, 2, 3].map(index => (
                      <div
                        key={index}
                        className={`h-1.5 flex-1 rounded-full ${
                          index < strength ? STRENGTH_BARS[strength] : 'bg-gray-200'
                        }`}
                      />
                    ))}
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    Password strength: {STRENGTH_LABELS[strength]}
                  </p>
                </div>
              )}
            </Field>

            <Field label="Confirm password" error={invalid('confirm_password')}>
              <input
                id="su-confirm"
                type="password"
                className="input-field"
                value={form.confirm_password}
                onChange={(e: ChangeEvent<HTMLInputElement>) =>
                  update('confirm_password', e.target.value)
                }
                onBlur={() => setTouched(t => ({ ...t, confirm_password: true }))}
                autoComplete="new-password"
                required
              />
            </Field>

            <button type="submit" className="btn-primary w-full" disabled={loading}>
              {loading ? <Spinner size={18} className="text-white" /> : 'Create account'}
            </button>
          </form>

          <p className="text-sm text-gray-600 text-center">
            Already registered?{' '}
            <button
              type="button"
              onClick={onSwitchToLogin}
              className="font-medium text-primary-600 hover:underline"
            >
              Sign in
            </button>
          </p>
        </div>
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
        <p className="text-xs text-gray-500 mt-1">{hint}</p>
      ) : null}
    </div>
  );
}
