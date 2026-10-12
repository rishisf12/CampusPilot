# CampusPilot Module Architecture

## Overview

This document describes the modular architecture of the CampusPilot frontend, migrated from a monolithic `features/` structure to a **four-module lazy-loaded architecture** using Vite's multi-entry build and React's `lazy`/`Suspense` for code splitting.

---

## Module Map

| Module | Programme Groups | Entry Point | Routes | Classroom Tabs |
|--------|------------------|-------------|--------|----------------|
| **student-ug** | UG (BTech, BDes) | `src/modules/student-ug/main.tsx` | `src/modules/student-ug/routes.tsx` | Live Schedule, Attendance, Vacant Rooms, Exam |
| **student-pg** | PG (MTech, MDes), PhD | `src/modules/student-pg/main.tsx` | `src/modules/student-pg/routes.tsx` | Live Schedule, Exam |
| **admin** | — | `src/modules/admin/main.tsx` | `src/modules/admin/routes.tsx` | — (Feedback Responses, Web Monitoring, Android Monitoring, Profile) |
| **faculty** | — | `src/modules/faculty/main.tsx` | `src/modules/faculty/routes.tsx` | — (placeholder) |

---

## Directory Structure

```
src/
├── api.ts                          # API client (re-exports from shared/)
├── core/
│   └── App.tsx                     # Root router (chooses module by role/programme)
├── main.tsx                        # App entry point (renders core/App)
├── shared/                         # Pure shared layer (zero feature imports)
│   ├── auth/                       # AuthWrapper + all 13 auth screens
│   ├── components/
│   │   ├── ErrorBanner.tsx
│   │   ├── Spinner.tsx
│   │   ├── NavIcons.tsx            # SECTION_ICONS, SECTION_LABELS
│   │   ├── FileUpload.tsx
│   │   ├── UploadPreview.tsx
│   │   ├── StatusCard.tsx
│   │   └── ModuleErrorBoundary.tsx # Per-module error isolation
│   ├── hooks/
│   │   ├── useProfile.tsx          # ProfileProvider, useProfile
│   │   ├── useProfileVersion.tsx
│   │   ├── useProfileCourses.tsx
│   │   └── useLiveDay.tsx
│   ├── lib/
│   │   ├── storage.ts              # localStorage helpers
│   │   ├── time.ts                 # Time formatting, IST helpers
│   │   ├── sync.ts                 # Profile/timetable change hooks
│   │   ├── passkey.ts              # WebAuthn helpers
│   │   └── normalise.ts            # Data normalisation
│   ├── types/
│   │   └── api.ts                  # Shared API types
│   ├── constants.ts                # GROUP_CLASSROOM_TABS, NAV_TABS, programmeGroupOf, etc.
│   └── features/
│       └── profile/Profile.tsx     # Shared by all student modules
├── modules/
│   ├── student-ug/
│   │   ├── features/
│   │   │   ├── schedule/LiveSchedule.tsx
│   │   │   ├── attendance/Attendance.tsx
│   │   │   ├── rooms/VacantRoomLookup.tsx
│   │   │   ├── exams/ExamSeating.tsx
│   │   │   ├── teams/ (6 files)
│   │   │   └── feedback/Feedback.tsx
│   │   ├── routes.tsx
│   │   └── main.tsx
│   ├── student-pg/
│   │   ├── features/
│   │   │   ├── schedule/LiveSchedule.tsx
│   │   │   ├── exams/ExamSeating.tsx
│   │   │   ├── teams/ (6 files)
│   │   │   └── feedback/Feedback.tsx
│   │   ├── routes.tsx
│   │   └── main.tsx
│   ├── admin/
│   │   ├── features/
│   │   │   ├── admin/ (AdminPanel, AdminLogin, ReinforcementPatterns)
│   │   │   └── monitoring/ (Monitoring + 6 panels + components)
│   │   ├── routes.tsx
│   │   └── main.tsx
│   └── faculty/
│       ├── features/ (empty)
│       ├── routes.tsx
│       └── main.tsx
├── tests/
│   └── passkey.test.ts
├── index.css
└── telemetry.ts
```

---

## Routing Logic (`src/core/App.tsx`)

```tsx
const StudentUGModule = lazy(() => import('@modules/student-ug/main'));
const StudentPGModule = lazy(() => import('@modules/student-pg/main'));
const AdminModule = lazy(() => import('@modules/admin/main'));
const FacultyModule = lazy(() => import('@modules/faculty/main'));

function AppRouter() {
  const { user } = useAuth();
  
  if (user?.role === 'admin') return <AdminModule />;
  if (user?.role === 'faculty') return <FacultyModule />;
  
  const group = programmeGroupOf(user?.programme);
  
  if (group === 'UG') {
    return (
      <ProfileProvider>
        <Suspense fallback={<Loading />}>
          <StudentUGModule />
        </Suspense>
      </ProfileProvider>
    );
  }
  
  // PG + PhD
  return (
    <ProfileProvider>
      <Suspense fallback={<Loading />}>
        <StudentPGModule />
      </Suspense>
    </ProfileProvider>
  );
}
```

---

## Vite Configuration

```ts
// vite.config.ts
build: {
  rollupOptions: {
    input: {
      main: 'index.html',
      'module-student-ug': 'src/modules/student-ug/main.tsx',
      'module-student-pg': 'src/modules/student-pg/main.tsx',
      'module-admin': 'src/modules/admin/main.tsx',
      'module-faculty': 'src/modules/faculty/main.tsx',
    },
  },
  chunkSizeWarningLimit: 500,  // kB
}
```

**Output chunks (production build):**
| Chunk | Size | Gzipped |
|-------|------|---------|
| module-student-ug | ~7 kB | ~2.6 kB |
| module-student-pg | ~6.7 kB | ~2.5 kB |
| module-admin | ~4.2 kB | ~1.7 kB |
| module-faculty | ~0.9 kB | ~0.5 kB |
| client (shared) | ~142 kB | ~45 kB |

---

## Key Design Decisions

### 1. Shared Layer is Pure
- **Zero imports from `features/`** — verified by `grep -r "from.*features" src/shared`
- All components in `shared/` can be used by any module without pulling in feature code
- AuthWrapper, ProfileProvider, and all auth screens live in `shared/auth/`

### 2. Single Source of Truth for Feature Gating
- `GROUP_CLASSROOM_TABS` in `shared/constants.ts` defines which tabs each programme group sees
- Modules **import** this, never duplicate it
- UG: `['live', 'attendance', 'vacant', 'exam']`
- PG/PhD: `['live', 'exam']`

### 3. Vite Aliases for Clean Imports
```ts
// tsconfig.json + vite.config.ts
'@/*': ['src/*'],
'@shared/*': ['src/shared/*'],
'@modules/*': ['src/modules/*']
```

Usage:
```ts
import { useAuth } from '@shared/auth/AuthWrapper';
import { useProfile } from '@shared/hooks/useProfile';
import { GROUP_CLASSROOM_TABS } from '@shared/constants';
import LiveSchedule from './features/schedule/LiveSchedule';  // relative within module
```

### 4. Error Isolation per Module
Each module's content is wrapped in `ModuleErrorBoundary`:
```tsx
<ModuleErrorBoundary moduleName="student-ug">
  <Suspense fallback={<Loading />}>
    {/* module content */}
  </Suspense>
</ModuleErrorBoundary>
```
- A crash in one module doesn't white-screen the entire app
- Header, footer, and other modules remain functional
- Error UI includes reload button and collapsible stack trace

### 5. Lazy Loading with Suspense
- Each feature is loaded via `React.lazy()` when its tab/section is accessed
- Shared components (Profile, NavIcons) are in the main chunk
- Module-specific code only downloads when needed

### 6. ProfileProvider Scoping
- Student modules (UG/PG) are wrapped in `ProfileProvider` so `useProfile()` works
- Admin module does NOT wrap in ProfileProvider (admins don't have student profiles)
- Profile component is shared via `@shared/features/profile/Profile`

---

## Migration Checklist (Completed)

- [x] Phase 0: Baseline commit, all checks pass
- [x] Phase 1: Harden `shared/`, move AuthWrapper + Profile, add aliases
- [x] Phase 2: Create module scaffolding, multi-entry Vite config, core/App.tsx
- [x] Phase 3: Migrate Student-UG (7 features, full routing, delete duplicates)
- [x] Phase 4: Migrate Student-PG (4 features, PG-only classroom tabs)
- [x] Phase 5: Migrate Admin (admin + monitoring features)
- [x] Phase 6: Faculty placeholder
- [x] Phase 7: Delete old `features/`, relocate tests
- [x] Phase 8: Error boundaries, size budgets, docs

---

## Developer Workflow

### Adding a New Feature to a Module
1. Create component in `src/modules/<module>/features/<feature>/`
2. Import shared utilities via `@shared/*` aliases
3. Add route/tab in the module's `routes.tsx`
4. Run `npx tsc --noEmit && npx eslint src --ext .ts,.tsx && npx vitest run`

### Adding a Shared Component
1. Add to `src/shared/components/` or appropriate subdirectory
2. Export from `src/shared/components/index.ts` (or import directly)
3. Use `@shared/components/ComponentName` in any module

### Changing Classroom Tabs for a Programme Group
1. Edit `GROUP_CLASSROOM_TABS` in `src/shared/constants.ts`
2. All modules automatically respect the change

### Debugging Module Load
- Open DevTools Network tab → filter by "module-"
- Each module chunk loads on first access to that role/programme
- Suspense fallback shows spinner while chunk downloads

---

## Common Commands

```bash
# Type-check
npx tsc --noEmit

# Lint
npx eslint src --ext .ts,.tsx

# Unit tests
npx vitest run

# Production build
npx vite build

# Dev server
npx vite --port 5173

# Check bundle sizes
npx vite build 2>&1 | grep "module-"
```

---

## Future Work

1. **E2E Tests** — Add Playwright tests for each module's critical paths
2. **Faculty Module** — Implement when backend APIs are ready
3. **Module Preloading** — Consider `prefetch` for likely next modules
4. **Analytics** — Track module load times and error rates per module
5. **Shared UI Library** — Extract common components to a versioned package if reused across repos

---

## Appendix: Module Size Budgets

| Module | Warning Limit | Current (gzip) | Status |
|--------|---------------|----------------|--------|
| student-ug | 500 kB | 2.6 kB | ✅ |
| student-pg | 500 kB | 2.5 kB | ✅ |
| admin | 500 kB | 1.7 kB | ✅ |
| faculty | 500 kB | 0.5 kB | ✅ |

Configured in `vite.config.ts`:
```ts
build: {
  chunkSizeWarningLimit: 500,
}
```

Build fails if any module chunk exceeds 500 kB (uncompressed).