import { useState, FormEvent, ChangeEvent } from 'react';
import { authApi } from '../api';
import ErrorBanner from './ErrorBanner';
import Spinner from './Spinner';

/**
 * Password reset by emailed code - the fallback when the passkey route does not
 * apply.
 *
 * Two steps, because the code has to arrive before a password can be set:
 *
 *   1. enter a username (or email) and ask for a code
 *   2. enter that code plus a new password
 *
 * Step 1 never says whether the account exists. That is the server's doing, and
 * repeating it here would only invite a client-side guess - so the same neutral
 * message is shown either way.
 *
 * Resetting does more than change the password: it signs out every device and
 * removes every passkey. That is stated up front, before any code is sent,
 * because it is the kind of consequence people are surprised by afterwards.
 */
interface PasswordResetProps {
  onBack: () => void;
  onDone?: (data: { message: string; passkeys_revoked?: number }) => void;
  offline: boolean;
}

export default function PasswordReset({ onBack, onDone, offline }: PasswordResetProps) {
  const [step, setStep] = useState<'ask' | 'code'>('ask');
  const [identifier, setIdentifier] = useState('');
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const askForCode = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    if (!identifier.trim()) {
      setError('Enter your username or email');
      return;
    }
    setBusy(true);
    try {
      const data = await authApi.forgotPassword(identifier.trim());
      setNotice(data.message);
      setStep('code');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send code');
    } finally {
      setBusy(false);
    }
  };

  const setNewPassword = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    if (!code.trim()) {
      setError('Enter the code from your email');
      return;
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }
    if (password !== confirm) {
      setError('The two passwords do not match');
      return;
    }

    setBusy(true);
    try {
      const data = await authApi.resetPassword(identifier.trim(), code.trim(), password);
      // Passkeys went with the password, so the student has to sign in again.
      onDone?.(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reset password');
    } finally {
      setBusy(false);
    }
  };

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
          {offline && (
            <div className="p-3 rounded-lg border border-warning-200 bg-warning-50 text-warning-700 text-sm">
              Backend offline. Start it with: uvicorn main:app --port 8000
            </div>
          )}

          <div>
            <h2 className="text-lg font-semibold text-gray-900">Reset your password</h2>
            <p className="text-sm text-gray-600 mt-1">
              We will email a code to the address on your account. Use it to set a new password.
            </p>
          </div>

          {/* Said before anything is sent, so it is a choice rather than a surprise. */}
          <div className="p-3 rounded-lg border border-warning-200 bg-warning-50 text-warning-700 text-sm space-y-1">
            <p className="font-medium">Setting a new password will also:</p>
            <ul className="list-disc list-inside space-y-0.5">
              <li>sign you out on every device</li>
              <li>remove any passkeys on your account</li>
            </ul>
            <p className="text-warning-600">
              That is deliberate - it is what stops whoever prompted the reset from staying signed
              in.
            </p>
          </div>

          <ErrorBanner message={error} onDismiss={() => setError(null)} />

          {notice && (
            <div className="p-3 rounded-lg border border-success-200 bg-success-50 text-success-700 text-sm">
              {notice}
            </div>
          )}

          {step === 'ask' ? (
            <form onSubmit={askForCode} className="space-y-4">
              <div>
                <label className="label" htmlFor="reset-identifier">
                  Username or email
                </label>
                <input
                  id="reset-identifier"
                  name="identifier"
                  className="input-field"
                  value={identifier}
                  onChange={(event: ChangeEvent<HTMLInputElement>) => {
                    setIdentifier(event.target.value);
                    setError(null);
                  }}
                  autoComplete="username"
                  placeholder="your username"
                />
              </div>
              <button type="submit" className="btn-primary w-full" disabled={busy}>
                {busy ? <Spinner size={18} className="text-white" /> : 'Send reset code'}
              </button>
            </form>
          ) : (
            <form onSubmit={setNewPassword} className="space-y-4">
              <div>
                <label className="label" htmlFor="reset-code">
                  Code from your email
                </label>
                <input
                  id="reset-code"
                  name="code"
                  className="input-field font-mono tracking-widest"
                  value={code}
                  onChange={(event: ChangeEvent<HTMLInputElement>) => {
                    setCode(event.target.value);
                    setError(null);
                  }}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  placeholder="6-digit code"
                />
              </div>

              <div>
                <label className="label" htmlFor="reset-password">
                  New password
                </label>
                <input
                  id="reset-password"
                  name="new-password"
                  type="password"
                  className="input-field"
                  value={password}
                  onChange={(event: ChangeEvent<HTMLInputElement>) => {
                    setPassword(event.target.value);
                    setError(null);
                  }}
                  autoComplete="new-password"
                />
              </div>

              <div>
                <label className="label" htmlFor="reset-confirm">
                  Confirm new password
                </label>
                <input
                  id="reset-confirm"
                  name="confirm-password"
                  type="password"
                  className="input-field"
                  value={confirm}
                  onChange={(event: ChangeEvent<HTMLInputElement>) => {
                    setConfirm(event.target.value);
                    setError(null);
                  }}
                  autoComplete="new-password"
                />
              </div>

              <button type="submit" className="btn-primary w-full" disabled={busy}>
                {busy ? <Spinner size={18} className="text-white" /> : 'Set new password'}
              </button>

              <p className="text-center text-xs text-gray-500">
                Did not get it?{' '}
                <button
                  type="button"
                  onClick={() => {
                    setNotice(null);
                    setError(null);
                    setStep('ask');
                  }}
                  className="text-primary-600 hover:text-primary-500"
                >
                  Send it again
                </button>
              </p>
            </form>
          )}

          <div className="border-t border-gray-200 pt-3 text-center">
            <p className="text-sm text-gray-600">
              Have your password?{' '}
              <button
                type="button"
                onClick={onBack}
                className="font-medium text-primary-600 hover:text-primary-500"
              >
                Back to sign in
              </button>
              {' · '}
              <button
                type="button"
                onClick={onBack}
                className="font-medium text-primary-600 hover:text-primary-500"
              >
                Use a passkey
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
