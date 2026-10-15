import { useCallback, useEffect, useState } from 'react';
import { KeyRound, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui';
import { authApi } from '../../api';
import { createPasskey, isPasskeySupported } from '../lib/passkey';
import { getToken } from '../lib/storage';
import ErrorBanner from '../components/ErrorBanner';

/**
 * Manage the passkeys on this account.
 *
 * Two jobs: adding a device, and revoking one that is lost. Revoking is the
 * point - a passkey on a laptop that is no longer yours is a way into the
 * account that the owner can no longer see, so it has to be removable.
 *
 * Removing the last passkey is allowed. It is a deliberate loss of the
 * passwordless route, so it asks for confirmation first and says plainly what
 * will happen - after that the only way in is the password again.
 */

interface PasskeyItem {
  credential_id: string;
  label: string;
  created_at: string | null;
  last_used_at?: string | null;
}

export default function ManagePasskeys() {
  const [passkeys, setPasskeys] = useState<PasskeyItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | 'add' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  // The credential awaiting confirmation, so only that row shows the prompt.
  const [confirmingId, setConfirmingId] = useState<string | null>(null);

  const supported = isPasskeySupported();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await authApi.passkeys();
      setPasskeys(Array.isArray(data.passkeys) ? data.passkeys : []);
      setError(null);
    } catch (err) {
      // The account is still usable without this list, so say so and move on.
      setError(err instanceof Error ? err.message : 'Failed to load passkeys');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const addDevice = async () => {
    setError(null);
    setMessage(null);
    setBusy('add');
    try {
      const result = await createPasskey({ token: getToken() ?? '' });
      setMessage(`Passkey added for ${result.passkey.label}.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add passkey');
    } finally {
      setBusy(null);
    }
  };

  const removeDevice = async (credentialId: string) => {
    setError(null);
    setMessage(null);
    setBusy(credentialId);
    try {
      await authApi.removePasskey(credentialId);
      setMessage(
        passkeys.length === 1
          ? 'Last passkey removed. Your password is now the only way to sign in.'
          : 'Passkey removed.'
      );
      setConfirmingId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to remove passkey');
    } finally {
      setBusy(null);
    }
  };

  /** "Added 2 days ago" reads better than an absolute date for a recent action. */
  const describeAge = (iso: string | null | undefined): string => {
    if (!iso) return 'Never used';
    const then = new Date(iso);
    if (Number.isNaN(then.getTime())) return '';
    const days = Math.floor((Date.now() - then.getTime()) / 86400000);
    if (days <= 0) return 'Added today';
    if (days === 1) return 'Added yesterday';
    if (days < 30) return `Added ${days} days ago`;
    return `Added ${then.toLocaleDateString()}`;
  };

  const lastUsed = (iso: string | null | undefined): string => {
    if (!iso) return 'Never used';
    const then = new Date(iso);
    if (Number.isNaN(then.getTime())) return '';
    const days = Math.floor((Date.now() - then.getTime()) / 86400000);
    if (days <= 0) return 'Last used today';
    if (days === 1) return 'Last used yesterday';
    if (days < 30) return `Last used ${days} days ago`;
    return `Last used ${then.toLocaleDateString()}`;
  };

  return (
    <div className="neu-raised p-6 space-y-4">
      <div>
        <h3 className="text-sm font-semibold" style={{ color: 'var(--cp-text)' }}>
          Passkeys
        </h3>
        <p className="text-xs mt-0.5" style={{ color: 'var(--cp-muted)' }}>
          Sign in with your fingerprint, face or device PIN instead of your password. Remove a
          passkey if you lose the device that holds it.
        </p>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {message && (
        <div className="p-3 rounded-lg border border-success-200 bg-success-50 text-success-700 text-sm">
          {message}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-4">
          <Button variant="ghost" loading aria-label="Loading passkeys" />
        </div>
      ) : passkeys.length === 0 ? (
        <p className="text-sm" style={{ color: 'var(--cp-muted)' }}>
          No passkeys yet. Add one and you can sign in without typing your password - and get back
          in if you forget it.
        </p>
      ) : (
        <ul className="space-y-2">
          {passkeys.map(item => (
            <li
              key={item.credential_id}
              className="neu-inset rounded-xl px-3 py-2.5 flex items-center justify-between gap-3"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium truncate" style={{ color: 'var(--cp-text)' }}>
                  {item.label}
                </p>
                <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
                  {describeAge(item.created_at)} &middot; {lastUsed(item.last_used_at)}
                </p>
              </div>

              {confirmingId === item.credential_id ? (
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-xs" style={{ color: 'var(--cp-muted)' }}>
                    {passkeys.length === 1 ? 'Remove your only passkey?' : 'Remove?'}
                  </span>
                  <Button
                    type="button"
                    variant="danger"
                    size="sm"
                    icon={<Trash2 size={16} />}
                    loading={busy === item.credential_id}
                    onClick={() => removeDevice(item.credential_id)}
                  >
                    Yes, remove
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => setConfirmingId(null)}
                  >
                    Cancel
                  </Button>
                </div>
              ) : (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  icon={<Trash2 size={16} />}
                  onClick={() => setConfirmingId(item.credential_id)}
                  aria-label={`Remove passkey ${item.label}`}
                >
                  Remove
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="button"
          variant="primary"
          size="sm"
          icon={<KeyRound size={16} />}
          loading={busy === 'add'}
          onClick={addDevice}
          disabled={busy === 'add' || !supported}
        >
          Add a passkey
        </Button>
        {!supported && (
          <span className="text-xs" style={{ color: 'var(--cp-muted)' }}>
            This browser does not support passkeys. Chrome, Edge and Safari all do.
          </span>
        )}
      </div>
    </div>
  );
}
