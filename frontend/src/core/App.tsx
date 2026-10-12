import { Suspense, lazy } from 'react';
import AuthWrapper, { useAuth } from '@shared/auth/AuthWrapper';
import { programmeGroupOf } from '@shared/constants';
import { ProfileProvider } from '@shared/hooks/useProfile';

/** Lazy-loaded module entry points */
const StudentUGModule = lazy(() => import('@modules/student-ug/main'));
const StudentPGModule = lazy(() => import('@modules/student-pg/main'));
const AdminModule = lazy(() => import('@modules/admin/main'));
const FacultyModule = lazy(() => import('@modules/faculty/main'));

/** Simple loading fallback while a module chunk loads */
function ModuleLoading() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
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

function AppRouter() {
  const { user } = useAuth();

  // Admin sees the admin module regardless of programme
  if ((user?.role || 'student') === 'admin') {
    return (
      <Suspense fallback={<ModuleLoading />}>
        <AdminModule />
      </Suspense>
    );
  }

  // Faculty (future)
  if ((user?.role || 'student') === 'faculty') {
    return (
      <Suspense fallback={<ModuleLoading />}>
        <FacultyModule />
      </Suspense>
    );
  }

  // Student: route by programme group
  const group = programmeGroupOf(user?.programme);

  if (group === 'UG') {
    return (
      <ProfileProvider>
        <Suspense fallback={<ModuleLoading />}>
          <StudentUGModule />
        </Suspense>
      </ProfileProvider>
    );
  }

  // PG + PHD both use the student-pg module
  return (
    <ProfileProvider>
      <Suspense fallback={<ModuleLoading />}>
        <StudentPGModule />
      </Suspense>
    </ProfileProvider>
  );
}
