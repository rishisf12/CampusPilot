import { useState } from 'react';
import { KeyRound } from 'lucide-react';
import { Button, Modal } from '@/components/ui';
import { createPasskey, isPasskeySupported } from '../lib/passkey';

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
    <Modal title="Sign in with a passkey?" onClose={onDismiss}>
      <div className="space-y-4">
        <div>
          <p className="text-sm mt-1" style={{ color: 'var(--cp-muted)' }}>
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
          <p className="text-sm" style={{ color: 'var(--cp-muted)' }}>
            This browser does not support passkeys. Chrome, Edge and Safari all do.
          </p>
        ) : (
          <div className="flex gap-2">
            <Button
              type="button"
              variant="primary"
              icon={<KeyRound size={18} />}
              loading={busy}
              onClick={setUp}
              className="flex-1"
            >
              Set up passkey
            </Button>
            <Button type="button" variant="secondary" onClick={onDismiss} disabled={busy}>
              Not now
            </Button>
          </div>
        )}

        {!supported && (
          <Button type="button" variant="secondary" onClick={onDismiss} className="w-full">
            Close
          </Button>
        )}
      </div>
    </Modal>
  );
}
