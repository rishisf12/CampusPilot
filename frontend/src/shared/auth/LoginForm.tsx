import { useEffect, useState, FormEvent } from 'react';
import { LogIn, User, Lock, Loader2 } from 'lucide-react';
import { clearEmailJustVerified, readEmailJustVerified } from '../lib/storage';
import ErrorBanner from '../components/ErrorBanner';

import AuthLayout from './AuthLayout';
import TextField from './TextField';

/**
 * Sign in. Username and password only - email is not accepted.
 *
 * "Forgot password?" opens the passkey recovery screen rather than a reset:
 * a reset would change the password, and the point is to get back in without
 * doing that.
 *
 * Presentation only: AuthLayout supplies the frame and TextField the fields.
 * The props, the validation, the submit handler and the state are unchanged, so
 * the auth flow and every id, name and autocomplete value are exactly as they
 * were.
 */
interface LoginFormProps {
  onSwitchToSignup: () => void;
  onLogin: (username: string, password: string) => Promise<unknown>;
  onForgotPassword: () => void;
  onChangeRole?: () => void;
  resetNotice?: string | null;
  onDismissResetNotice?: () => void;
  offline: boolean;
}

export default function LoginForm({
  onSwitchToSignup,
  onLogin,
  onForgotPassword,
  onChangeRole,
  resetNotice,
  onDismissResetNotice,
  offline,
}: LoginFormProps) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Acknowledge a just-completed verification once, then clear the flag.
  useEffect(() => {
    if (readEmailJustVerified()) {
      setNotice('Email verified. Sign in to continue.');
      clearEmailJustVerified();
    }
  }, []);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    if (!username.trim()) {
      setError('Username is required');
      return;
    }
    if (!password) {
      setError('Password is required');
      return;
    }
    setLoading(true);
    try {
      await onLogin(username.trim(), password);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout title="Sign in" onBack={onChangeRole}>
      {offline && (
        <div className="cp-note cp-note-warn">
          Backend offline. Start it with: uvicorn main:app --port 8000
        </div>
      )}
      {notice && <div className="cp-note cp-note-ok">{notice}</div>}
      {resetNotice && (
        <div className="cp-note cp-note-ok flex items-start justify-between gap-2">
          <span>{resetNotice}</span>
          <button
            type="button"
            onClick={onDismissResetNotice}
            className="cp-note-x"
            aria-label="Dismiss"
          >
            x
          </button>
        </div>
      )}
      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      <form onSubmit={submit} className="space-y-4">
        <TextField
          label="Username"
          id="login-username"
          name="username"
          value={username}
          onChange={value => {
            setUsername(value);
            setError(null);
          }}
          icon={<User size={17} />}
          autoComplete="username"
          required
          index={0}
        />

        <TextField
          label="Password"
          id="login-password"
          name="password"
          type="password"
          value={password}
          onChange={value => {
            setPassword(value);
            setError(null);
          }}
          icon={<Lock size={17} />}
          autoComplete="current-password"
          required
          index={1}
        />

        {/* The label lives inside the button so it is announced with it, and the
            spinner is fixed-width so swapping the text cannot shift the row. */}
        <button type="submit" className="cp-submit mt-1" disabled={loading}>
          {loading ? (
            <>
              <Loader2 size={17} className="animate-spin" aria-hidden />
              Signing in…
            </>
          ) : (
            <>
              <LogIn size={17} aria-hidden />
              Sign in
            </>
          )}
        </button>
      </form>

      {/* Below the button, as a secondary route rather than competing with it. */}
      <div className="text-center">
        <button type="button" onClick={onForgotPassword} className="cp-link">
          Forgot password?
        </button>
      </div>

      <p className="text-sm text-center pt-1" style={{ color: 'var(--cp-muted)' }}>
        No account?{' '}
        <button type="button" onClick={onSwitchToSignup} className="cp-link">
          Create one
        </button>
      </p>
    </AuthLayout>
  );
}
