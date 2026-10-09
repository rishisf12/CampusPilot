import { useState, FormEvent, ChangeEvent } from 'react';
import { authenticateWithPasskey, isPasskeySupported } from '../lib/passkey';
import ErrorBanner from './ErrorBanner';
import Spinner from './Spinner';

/**
 * Password recovery by passkey.
 *
 * The passkey route comes first because it changes nothing: the password stays
 * exactly as it is. If no passkey is set up, or the device holding it is gone,
 * "Reset password with email" is the way through - that one does change the
 * password, and says so before it starts.
 *
 * The username is optional but expected to be typed - without it the device
 * offers every passkey it holds, which is convenient but only works for
 * *discoverable* credentials. Hence the small "any passkey on this device" link
 * rather than a second full-sized button.
 */
interface PasskeyRecoveryProps {
  onSignedIn: (accessToken: string) => Promise<unknown>;
  onBack: () => void;
  onResetPassword: () => void;
  offline: boolean;
}

export default function PasskeyRecovery({
  onSignedIn,
  onBack,
  onResetPassword,
  offline,
}: PasskeyRecoveryProps) {
  const [username, setUsername] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const supported = isPasskeySupported();

  /** @param {boolean} skipUsername offer any passkey instead of this account's. */
  const signIn = async (skipUsername = false) => {
    setError(null);
    setNotice(null);

    const name = skipUsername ? '' : username.trim();
    if (!skipUsername && !name) {
      setError('Enter your username, or choose "use any passkey on this device".');
      return;
    }

    setBusy(true);
    try {
      const data = await authenticateWithPasskey({ username: name });
      await onSignedIn(data.access_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to sign in with passkey');
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
          {notice && (
            <div className="p-3 rounded-lg border border-success-200 bg-success-50 text-success-700 text-sm">
              {notice}
            </div>
          )}
          <ErrorBanner message={error} onDismiss={() => setError(null)} />

          <div>
            <h2 className="text-lg font-semibold text-gray-900">Forgot your password?</h2>
            <p className="text-sm text-gray-600 mt-1">
              Sign in with the passkey on this device instead. Your password stays exactly as it is
              - nothing is reset and nothing changes.
            </p>
          </div>

          {!supported ? (
            <div className="p-3 rounded-lg border border-warning-200 bg-warning-50 text-warning-700 text-sm">
              This browser does not support passkeys. Use Chrome, Edge or Safari, or ask your
              department to reset the password.
            </div>
          ) : (
            <form
              onSubmit={(event: FormEvent<HTMLFormElement>) => {
                event.preventDefault();
                signIn(false);
              }}
              className="space-y-4"
            >
              <div>
                <label className="label" htmlFor="recovery-username">
                  Username
                </label>
                <input
                  id="recovery-username"
                  name="username"
                  className="input-field"
                  value={username}
                  onChange={(event: ChangeEvent<HTMLInputElement>) => {
                    setUsername(event.target.value);
                    setError(null);
                  }}
                  autoComplete="username webauthn"
                  placeholder="your username"
                />
              </div>

              <button type="submit" className="btn-primary w-full" disabled={busy}>
                {busy ? <Spinner size={18} className="text-white" /> : 'Continue with passkey'}
              </button>
            </form>
          )}

          {supported && (
            <button
              type="button"
              onClick={() => signIn(true)}
              disabled={busy}
              className="w-full text-sm text-primary-600 hover:text-primary-500 disabled:opacity-50"
            >
              Use any passkey on this device
            </button>
          )}

          {/* No passkey, or the device holding it is gone. */}
          <div className="border-t border-gray-200 pt-3 text-center">
            <button
              type="button"
              onClick={onResetPassword}
              disabled={busy}
              className="text-sm text-primary-600 hover:text-primary-500 disabled:opacity-50"
            >
              Reset password with email
            </button>
            <p className="text-xs text-gray-500 mt-2">
              {notice ? null : 'Needs a passkey set up already? Set one up after signing in.'}
            </p>
          </div>

          <div className="border-t border-gray-200 pt-3 text-center">
            <p className="text-sm text-gray-600">
              Remembered it?{' '}
              <button
                type="button"
                onClick={() => {
                  setError(null);
                  onBack();
                }}
                className="font-medium text-primary-600 hover:text-primary-500"
              >
                Back to sign in
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
