import { useCallback, useEffect, useState } from 'react';
import { authApi } from '../api';
import { createPasskey, isPasskeySupported } from '../lib/passkey';
import { getToken } from '../lib/storage';
import ErrorBanner from './ErrorBanner';
import Spinner from './Spinner';

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
    <div className="card space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-gray-900">Passkeys</h3>
        <p className="text-xs text-gray-500 mt-0.5">
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
          <Spinner size={20} className="text-primary-500" />
        </div>
      ) : passkeys.length === 0 ? (
        <p className="text-sm text-gray-600">
          No passkeys yet. Add one and you can sign in without typing your password - and get back
          in if you forget it.
        </p>
      ) : (
        <ul className="space-y-2">
          {passkeys.map(item => (
            <li
              key={item.credential_id}
              className="border border-gray-200 rounded-lg px-3 py-2.5 flex items-center justify-between gap-3"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">{item.label}</p>
                <p className="text-xs text-gray-500">
                  {describeAge(item.created_at)} &middot; {lastUsed(item.last_used_at)}
                </p>
              </div>

              {confirmingId === item.credential_id ? (
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-xs text-gray-600">
                    {passkeys.length === 1 ? 'Remove your only passkey?' : 'Remove?'}
                  </span>
                  <button
                    type="button"
                    onClick={() => removeDevice(item.credential_id)}
                    disabled={busy === item.credential_id}
                    className="px-2 py-1 text-xs font-medium rounded bg-danger-600 text-white hover:bg-danger-700 disabled:opacity-50"
                  >
                    {busy === item.credential_id ? 'Removing' : 'Yes, remove'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmingId(null)}
                    className="px-2 py-1 text-xs text-gray-600 hover:text-gray-900"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setConfirmingId(item.credential_id)}
                  className="shrink-0 text-xs font-medium text-danger-600 hover:text-danger-700"
                >
                  Remove
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={addDevice}
          disabled={busy === 'add' || !supported}
          className="btn-primary text-sm"
        >
          {busy === 'add' ? <Spinner size={16} className="text-white" /> : 'Add a passkey'}
        </button>
        {!supported && (
          <span className="text-xs text-gray-500">
            This browser does not support passkeys. Chrome, Edge and Safari all do.
          </span>
        )}
      </div>
    </div>
  );
}
