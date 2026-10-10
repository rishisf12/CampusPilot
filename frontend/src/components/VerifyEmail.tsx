import { useCallback, useEffect, useState } from 'react';
import { authApi } from '../api';
import { RESEND_COOLDOWN_SECONDS } from '../constants';
import { readPendingVerification, writePendingVerification } from '../lib/storage';
import ErrorBanner from './ErrorBanner';
import Spinner from './Spinner';

// AuthWrapper starts this clock when a signup completes, so the two must agree.
const COOLDOWN_SECONDS = RESEND_COOLDOWN_SECONDS;

/** Remaining whole seconds on the resend cooldown. */
function secondsLeft(timestamp: number | undefined | null): number {
  if (!timestamp) return 0;
  return Math.max(0, Math.ceil((Number(timestamp) - Date.now()) / 1000));
}

interface VerifyEmailProps {
  onVerified: () => void;
  onStartOver: () => void;
}

/**
 * 6-digit email verification.
 *
 * The pending address and its resend cooldown are stored together in
 * localStorage, so closing and reopening the tab returns to this screen with the
 * email prefilled and the cooldown still counting.
 */
export default function VerifyEmail({ onVerified, onStartOver }: VerifyEmailProps) {
  const [email, setEmail] = useState<string>('');
  const [code, setCode] = useState('');
  const [cooldown, setCooldown] = useState(() =>
    secondsLeft(readPendingVerification()?.resendAvailableAt)
  );
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (cooldown <= 0) return undefined;
    const timer = setInterval(
      () => setCooldown(secondsLeft(readPendingVerification()?.resendAvailableAt)),
      1000
    );
    return () => clearInterval(timer);
  }, [cooldown]);

  // Persist the address, keeping any cooldown already recorded.
  useEffect(() => {
    writePendingVerification(email, readPendingVerification()?.resendAvailableAt || 0);
  }, [email]);

  const verify = useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (code.trim().length !== 6) {
        setError('Enter the 6-digit code');
        return;
      }
      setLoading(true);
      setError(null);
      try {
        await authApi.verifyEmail({ email: email.trim().toLowerCase(), code: code.trim() });
        writePendingVerification('');
        onVerified();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Verification failed');
      } finally {
        setLoading(false);
      }
    },
    [code, email, onVerified]
  );

  const resend = async () => {
    setResending(true);
    setError(null);
    try {
      // Sent as an object body, as the endpoint expects.
      await authApi.resendVerificationCode({ email: email.trim().toLowerCase() });
      const until = Date.now() + COOLDOWN_SECONDS * 1000;
      writePendingVerification(email, until);
      setCooldown(COOLDOWN_SECONDS);
      setNotice('A new code is on its way.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resend code');
    } finally {
      setResending(false);
    }
  };

  const startOver = () => {
    // Clears the address and the cooldown together.
    writePendingVerification('');
    setCode('');
    onStartOver();
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="text-center mb-6">
          <img src="/logo-icon.svg" alt="Essential" className="w-14 h-14 mx-auto" />
          <h1 className="mt-2 text-2xl font-bold text-primary-500">Verify your email</h1>
          <p className="text-xs tracking-widest text-primary-400 font-medium">
            YOUR CAMPUS ASSISTANT
          </p>
        </div>

        <div className="card space-y-4">
          <p className="text-sm text-gray-600">
            We sent a 6-digit code to{' '}
            <span className="font-medium text-gray-900">{email || 'your email'}</span>.
          </p>

          {notice && (
            <div className="p-3 rounded-lg border border-success-200 bg-success-50 text-success-700 text-sm">
              {notice}
            </div>
          )}
          <ErrorBanner message={error} onDismiss={() => setError(null)} />

          <form onSubmit={verify} className="space-y-4">
            <div>
              <label className="label" htmlFor="verify-email">
                Email
              </label>
              <input
                id="verify-email"
                type="email"
                className="input-field"
                value={email}
                onChange={event => {
                  setEmail(event.target.value);
                  setError(null);
                }}
                required
              />
            </div>

            <div>
              <label className="label" htmlFor="verify-code">
                Verification code
              </label>
              <input
                id="verify-code"
                inputMode="numeric"
                maxLength={6}
                className="input-field text-center font-mono text-lg tracking-[0.4em]"
                value={code}
                onChange={event => {
                  setCode(event.target.value.replace(/\D/g, '').slice(0, 6));
                  setError(null);
                }}
                placeholder="000000"
                required
              />
            </div>

            <button
              type="submit"
              className="btn-primary w-full"
              disabled={loading || code.length !== 6}
            >
              {loading ? <Spinner size={18} className="text-white" /> : 'Verify email'}
            </button>
          </form>

          <div className="flex items-center justify-between text-sm pt-1">
            <button
              type="button"
              onClick={resend}
              disabled={cooldown > 0 || resending || !email}
              className="font-medium text-primary-600 hover:underline disabled:text-gray-400 disabled:no-underline"
            >
              {cooldown > 0
                ? `Resend Code in ${cooldown}s…`
                : resending
                  ? 'Sending…'
                  : 'Resend Code'}
            </button>
            <button type="button" onClick={startOver} className="text-gray-600 hover:underline">
              Wrong email? Start over
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
