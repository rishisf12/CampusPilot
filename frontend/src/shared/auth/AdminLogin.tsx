import { useState, FormEvent } from 'react';
import { LogIn, User, Lock, Loader2 } from 'lucide-react';
import ErrorBanner from '../components/ErrorBanner';

import AuthLayout from './AuthLayout';
import TextField from './TextField';

/**
 * Developer sign-in. Same username + password as students - the *role* on the
 * account is what opens the admin panel, and that role is granted with
 * `tools/make_admin.py`, never by signup.
 *
 * Presentation only. The props, the validation, the submit handler and the
 * state are unchanged, so the ids, names and autocomplete values are as they
 * were.
 */
interface AdminLoginProps {
  onLogin: (username: string, password: string) => Promise<unknown>;
  onBack: () => void;
  offline: boolean;
}

export default function AdminLogin({ onLogin, onBack, offline }: AdminLoginProps) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    <AuthLayout title="Admin sign in" onBack={onBack}>
      {offline && (
        <div className="cp-note cp-note-warn">
          Backend offline. Start it with: uvicorn main:app --port 8000
        </div>
      )}
      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      <form onSubmit={submit} className="space-y-4">
        <TextField
          label="Username"
          id="admin-username"
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
          id="admin-password"
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

        <button type="submit" className="cp-submit mt-1" disabled={loading}>
          {loading ? (
            <>
              <Loader2 size={17} className="animate-spin" aria-hidden />
              Signing in…
            </>
          ) : (
            <>
              <LogIn size={17} aria-hidden />
              Sign in as admin
            </>
          )}
        </button>
      </form>
    </AuthLayout>
  );
}
