import { Suspense, lazy } from 'react';
import AuthWrapper, { useAuth } from '@shared/auth/AuthWrapper';
import { programmeGroupOf } from '@shared/constants';
import { ProfileProvider } from '@shared/hooks/useProfile';
import { SettingsProvider } from '@shared/features/settings/SettingsProvider';
import { useApplyTheme } from '@shared/features/settings/useTheme';
import { useDisplayPrefs } from '@shared/features/settings/useDisplayPrefs';
import { useCachedLookupPolicy } from '@shared/features/settings/usePrivacyPrefs';

/** Lazy-loaded module entry points */
const StudentUGModule = lazy(() => import('@modules/student-ug/main'));
const StudentPGModule = lazy(() => import('@modules/student-pg/main'));
const AdminModule = lazy(() => import('@modules/admin/main'));
const FacultyModule = lazy(() => import('@modules/faculty/main'));

/** Simple loading fallback while a module chunk loads */
function ModuleLoading() {
  return (
    <div
      className="min-h-screen flex items-center justify-center"
      style={{ background: 'var(--cp-bg)' }}
    >
      <div className="w-8 h-8 border-4 border-primary-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

/**
 * Root app component.
 *
 * Wraps everything in AuthWrapper so the session is established before
 * we decide which module to load. The module is chosen by the user's
 * role (admin) or programme group (UG/PG/PHD).
 */
export default function App() {
  return (
    <AuthWrapper>
      <AppRouter />
    </AuthWrapper>
  );
}

/**
 * Applies the settings that change how the app behaves, not just how the
 * Settings page looks.
 *
 * Theme, density and motion become attributes on the document element, so one
 * component owns them all and plain CSS can respond without a value threaded
 * through every screen. The cached-lookup policy clears stored data when the
 * student switches it off.
 *
 * A component rather than bare hook calls so they sit *inside* SettingsProvider -
 * each reads the store, and calling one above the provider would throw. Renders
 * nothing.
 */
function SettingsEffects() {
  useApplyTheme();
  useDisplayPrefs();
  useCachedLookupPolicy();
  return null;
}

function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <ProfileProvider>
      <SettingsProvider>
        <SettingsEffects />
        {children}
      </SettingsProvider>
    </ProfileProvider>
  );
}

function AppRouter() {
  const { user } = useAuth();

  // Admin sees the admin module regardless of programme
  if ((user?.role || 'student') === 'admin') {
    return (
      <AppProviders>
        <Suspense fallback={<ModuleLoading />}>
          <AdminModule />
        </Suspense>
      </AppProviders>
    );
  }

  // Faculty (future)
  if ((user?.role || 'student') === 'faculty') {
    return (
      <AppProviders>
        <Suspense fallback={<ModuleLoading />}>
          <FacultyModule />
        </Suspense>
      </AppProviders>
    );
  }

  // Student: route by programme group
  const group = programmeGroupOf(user?.programme);

  if (group === 'UG') {
    return (
      <AppProviders>
        <Suspense fallback={<ModuleLoading />}>
          <StudentUGModule />
        </Suspense>
      </AppProviders>
    );
  }

  // PG + PHD both use the student-pg module
  return (
    <AppProviders>
      <Suspense fallback={<ModuleLoading />}>
        <StudentPGModule />
      </Suspense>
    </AppProviders>
  );
}
