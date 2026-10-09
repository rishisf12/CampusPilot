import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { authApi, isUnauthorized } from '../api';
import {
  bumpProfileVersion,
  clearSession,
  getToken,
  purgeObsoleteKeys,
  readPendingVerification,
  setEmailJustVerified,
  setToken,
  writeCachedUser,
} from '../lib/storage';
import LoginForm from './LoginForm';
import AdminLogin from '../features/admin/AdminLogin';
import PasskeyPrompt from './PasskeyPrompt';
import PasskeyRecovery from './PasskeyRecovery';
import PasswordReset from './PasswordReset';
import SignupEmail from './SignupEmail';
import SignupForm from './SignupForm';
import StartScreen from './StartScreen';
import VerifyEmail from './VerifyEmail';
import Spinner from './Spinner';

/**
 * Auth provider.
 *
 * Owns the session and decides which screen to show.  On reload the token is
 * re-validated with `/auth/me`, retrying twice so a backend that is still
 * starting does not log the user out.  Only a genuine 401 clears the session;
 * network failures keep the user signed in so the header can show "offline".
 */

interface User {
  id: number;
  email: string;
  username: string;
  is_email_verified: boolean;
  full_name?: string;
  roll_number?: string;
  role?: string;
}

interface AuthContextValue {
  user: User | null;
  logout: () => Promise<void>;
  refreshProfile: () => Promise<void>;
  offline: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used inside AuthWrapper');
  return value;
}

/** The email awaiting OTP verification, if any. */
export function readPendingEmail(): string {
  return readPendingVerification()?.email || '';
}

type Screen =
  'start' | 'login' | 'admin-login' | 'signup-email' | 'signup' | 'verify' | 'recover' | 'reset';

type Status = 'checking' | 'anonymous' | 'authenticated';

export default function AuthWrapper({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<Status>('checking');
  const [user, setUser] = useState<User | null>(null);
  const [screen, setScreen] = useState<Screen>('start');
  const [offline, setOffline] = useState(false);
  // Shown on the sign-in screen after a password reset completes.
  const [resetResult, setResetResult] = useState<string | null>(null);
  // The address proven by /signup/verify, which the details step then submits.
  const [verifiedEmail, setVerifiedEmail] = useState('');
  // Set after a password sign-in on an account with no passkey, to offer one.
  const [offerPasskey, setOfferPasskey] = useState(false);

  /**
   * Re-fetch the signed-in user and announce the change.
   *
   * Called on mount, after login, and by `refreshProfile()`. Retries twice so a
   * backend that is still starting does not log the user out; only a genuine 401
   * clears the session, because a network failure must not sign anyone out.
   */
  const refreshProfile = useCallback(async (retries = 2) => {
    if (!getToken()) {
      setStatus('anonymous');
      return;
    }
    for (let attempt = 0; attempt <= retries; attempt += 1) {
      try {
        const data = await authApi.me();
        setUser(data);
        // Cache for an instant first paint; the server stays the source of truth.
        writeCachedUser(data);
        setOffline(false);
        setStatus('authenticated');
        return;
      } catch (error) {
        if (isUnauthorized(error)) {
          clearSession();
          setUser(null);
          setStatus('anonymous');
          return;
        }
        // Backend unreachable: wait and retry rather than dropping the session.
        setOffline(true);
        if (attempt < retries) {
          await new Promise(resolve => setTimeout(resolve, 1500));
        }
      }
    }
    // Still unreachable - keep the session, let the app render offline.
    setStatus('authenticated');
  }, []);

  useEffect(() => {
    // Clear keys earlier versions wrote, so nothing stale shadows the backend.
    purgeObsoleteKeys();
    refreshProfile();
  }, [refreshProfile]);

  // A pending verification means the tab was closed mid-flow.
  useEffect(() => {
    if (status === 'anonymous' && readPendingEmail()) setScreen('verify');
  }, [status]);

  /**
   * Sign in with a token that is already in hand.
   *
   * Shared by the password and passkey paths so both end up in an identical
   * session: the token is stored, the user is fetched, and the app is told to
   * re-sync.
   */
  const adoptSession = useCallback(async (accessToken: string): Promise<User> => {
    setToken(accessToken);
    const profile = await authApi.me();
    setUser(profile);
    writeCachedUser(profile);
    setOffline(false);
    setStatus('authenticated');
    // A fresh sign-in re-syncs attendance, since the profile drives it.
    bumpProfileVersion();
    return profile;
  }, []);

  /**
   * Should a passkey be offered now?
   *
   * Only after a password sign-in, and only when the account has none: this is
   * the moment the student can prove who they are. A failed check must not block
   * sign-in, so the offer is simply skipped if the endpoint is unavailable.
   */
  const maybeOfferPasskey = useCallback(async () => {
    try {
      const data = await authApi.passkeys();
      setOfferPasskey(!data.has_passkey);
    } catch {
      /* no passkey info available - do not interrupt the sign-in */
    }
  }, []);

  const handleLogin = async (username: string, password: string) => {
    const data = await authApi.login(username, password);
    const profile = await adoptSession(data.access_token);
    maybeOfferPasskey();
    return profile;
  };

  /**
   * Admin sign-in for the developer. Same credentials flow, but the account
   * must carry the admin role - otherwise the session is dropped immediately
   * with an explanation, so a student mistyping here is never left signed in
   * as something they are not.
   */
  const handleAdminLogin = async (username: string, password: string) => {
    const data = await authApi.login(username, password);
    const profile = await adoptSession(data.access_token);
    if ((profile?.role || 'student') !== 'admin') {
      clearSession();
      setUser(null);
      setStatus('anonymous');
      setScreen('admin-login');
      throw new Error(
        'This account is not an admin. Ask the developer to run tools/make_admin.py.'
      );
    }
    return profile;
  };

  const handleLogout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      /* the client-side token removal is what actually ends the session */
    }
    clearSession();
    setUser(null);
    setStatus('anonymous');
    setScreen('login');
    setOfferPasskey(false);
  }, []);

  if (status === 'checking') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Spinner size={32} className="text-primary-500" />
      </div>
    );
  }

  if (status === 'anonymous') {
    // The role question comes first. Student and admin both sign in here;
    // faculty is still on the way.
    if (screen === 'start') {
      return (
        <StartScreen
          onChooseStudent={() => setScreen('login')}
          onChooseAdmin={() => setScreen('admin-login')}
        />
      );
    }

    if (screen === 'admin-login') {
      return (
        <AdminLogin
          offline={offline}
          onBack={() => setScreen('start')}
          onLogin={handleAdminLogin}
        />
      );
    }

    if (screen === 'signup-email') {
      return (
        <SignupEmail
          offline={offline}
          onBack={() => setScreen('login')}
          onVerified={email => {
            // Proof of the address, so the details step below can create the
            // account. Kept in state, not storage: a reload re-asks for the code
            // rather than trusting a value the page no longer holds.
            setVerifiedEmail(email);
            setScreen('signup');
          }}
        />
      );
    }

    if (screen === 'signup') {
      return (
        <SignupForm
          verifiedEmail={verifiedEmail}
          onSwitchToLogin={() => setScreen('login')}
          onRegistered={() => {
            // The address is already proven, so the flag only drives a welcome.
            setEmailJustVerified();
            setVerifiedEmail('');
            setScreen('login');
          }}
          onStartOver={() => {
            setVerifiedEmail('');
            setScreen('signup-email');
          }}
        />
      );
    }

    if (screen === 'verify') {
      return (
        <VerifyEmail
          onVerified={() => {
            setScreen('login');
            // The flag makes the login form acknowledge the verification once.
            setEmailJustVerified();
          }}
          onStartOver={() => setScreen('signup-email')}
        />
      );
    }
    if (screen === 'recover') {
      return (
        <PasskeyRecovery
          offline={offline}
          onSignedIn={adoptSession}
          onBack={() => setScreen('login')}
          onResetPassword={() => setScreen('reset')}
        />
      );
    }
    if (screen === 'reset') {
      return (
        <PasswordReset
          offline={offline}
          onBack={() => setScreen('recover')}
          // A reset invalidates every session, so land back on sign-in with the
          // outcome shown rather than pretending anything is still signed in.
          onDone={result => {
            setScreen('login');
            setResetResult(
              `${result.message}${result.passkeys_revoked ? ' Passkeys were removed too.' : ''}`
            );
          }}
        />
      );
    }
    return (
      <LoginForm
        onSwitchToSignup={() => setScreen('signup-email')}
        onLogin={handleLogin}
        onForgotPassword={() => setScreen('recover')}
        onChangeRole={() => setScreen('start')}
        resetNotice={resetResult}
        onDismissResetNotice={() => setResetResult(null)}
        offline={offline}
      />
    );
  }

  return (
    <AuthContext.Provider value={{ user, logout: handleLogout, refreshProfile, offline }}>
      {children}
      {/* Offered over the app, not instead of it: dismissing it just closes. */}
      {offerPasskey && (
        <PasskeyPrompt
          token={getToken() ?? ''}
          onEnrolled={() => setOfferPasskey(false)}
          onDismiss={() => setOfferPasskey(false)}
        />
      )}
    </AuthContext.Provider>
  );
}
