import { useState } from 'react';
import { createPasskey, isPasskeySupported } from '../lib/passkey';
import Spinner from './Spinner';

/**
 * The one-time prompt offering to enrol a passkey after a password sign-in.
 *
 * Shown only when the account has no passkey yet, which makes it a first-login
 * moment - the one time a student is guaranteed to have their password in hand
 * and can therefore prove who they are. Enrolling afterwards, from a settings
 * screen, would be the weaker choice.
 *
 * Dismissible on purpose. A student who is in a hurry, on a shared machine, or
 * simply does not want one should be able to say no and carry on - the offer
 * returns on the next sign-in, so nothing is lost by declining.
 */
interface PasskeyPromptProps {
  token: string;
  onEnrolled?: (passkey: unknown) => void;
  onDismiss: () => void;
}

export default function PasskeyPrompt({ token, onEnrolled, onDismiss }: PasskeyPromptProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const supported = isPasskeySupported();

  const setUp = async () => {
    setError(null);
    setBusy(true);
    try {
      const result = await createPasskey({ token });
      onEnrolled?.(result.passkey);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create passkey');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-sm rounded-xl bg-white shadow-xl p-5 space-y-4">
        <div>
          <h3 className="text-base font-semibold text-gray-900">Sign in with a passkey?</h3>
          <p className="text-sm text-gray-600 mt-1">
            Use your fingerprint, face or device PIN next time instead of your password. If you ever
            forget your password, a passkey gets you back in without changing it.
          </p>
        </div>

        {error && (
          <div className="p-3 rounded-lg border border-danger-200 bg-danger-50 text-danger-700 text-sm">
            {error}
          </div>
        )}

        {!supported ? (
          <p className="text-sm text-gray-500">
            This browser does not support passkeys. Chrome, Edge and Safari all do.
          </p>
        ) : (
          <div className="flex gap-2">
            <button type="button" onClick={setUp} disabled={busy} className="btn-primary flex-1">
              {busy ? <Spinner size={18} className="text-white" /> : 'Set up passkey'}
            </button>
            <button type="button" onClick={onDismiss} disabled={busy} className="btn-secondary">
              Not now
            </button>
          </div>
        )}

        {!supported && (
          <button type="button" onClick={onDismiss} className="btn-secondary w-full">
            Close
          </button>
        )}
      </div>
    </div>
  );
}
