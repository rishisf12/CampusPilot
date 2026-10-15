import { useState, FormEvent, ChangeEvent } from 'react';
import { LogIn, ArrowLeft } from 'lucide-react';
import { Button, Card, Input } from '@/components/ui';
import ErrorBanner from '../components/ErrorBanner';

/**
 * Developer sign-in. Same username + password as students - the *role* on the
 * account is what opens the admin panel, and that role is granted with
 * `tools/make_admin.py`, never by signup.
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
    <div
      className="min-h-screen flex items-center justify-center px-4 py-12"
      style={{ background: 'var(--cp-bg)' }}
    >
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <img src="/logo-icon.svg" alt="Essential" className="w-16 h-16 mx-auto" />
          <h1 className="mt-3 text-2xl font-bold text-primary-500">essential</h1>
          <p className="text-xs tracking-widest text-primary-400 font-medium">
            YOUR CAMPUS ASSISTANT
          </p>
        </div>

        <Card className="space-y-4">
          {offline && (
            <div className="p-3 rounded-lg border border-warning-200 bg-warning-50 text-warning-700 text-sm">
              Backend offline. Start it with: uvicorn main:app --port 8000
            </div>
          )}
          <ErrorBanner message={error} onDismiss={() => setError(null)} />

          <div>
            <h2 className="text-lg font-semibold" style={{ color: 'var(--cp-text)' }}>
              Admin sign in
            </h2>
            <p className="text-sm mt-1" style={{ color: 'var(--cp-muted)' }}>
              Developer access - feedback responses live here.
            </p>
          </div>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="label" htmlFor="admin-username">
                Username
              </label>
              <Input
                id="admin-username"
                name="username"
                value={username}
                onChange={(event: ChangeEvent<HTMLInputElement>) => {
                  setUsername(event.target.value);
                  setError(null);
                }}
                autoComplete="username"
                required
              />
            </div>

            <div>
              <label className="label" htmlFor="admin-password">
                Password
              </label>
              <Input
                id="admin-password"
                name="password"
                type="password"
                value={password}
                onChange={(event: ChangeEvent<HTMLInputElement>) => {
                  setPassword(event.target.value);
                  setError(null);
                }}
                autoComplete="current-password"
                required
              />
            </div>

            <Button
              type="submit"
              variant="primary"
              icon={<LogIn size={18} />}
              loading={loading}
              className="w-full"
            >
              Sign in as admin
            </Button>
          </form>

          <p className="text-center">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              icon={<ArrowLeft size={14} />}
              onClick={onBack}
            >
              Back to role choice
            </Button>
          </p>
        </Card>
      </div>
    </div>
  );
}
