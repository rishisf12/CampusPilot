# Phased Migration Plan: Frontend Module Architecture — CampusPilot

**Project**: CampusPilot (React + TypeScript + Vite)  
**Current State**: Single `src/` with `features/` (some duplication) and `shared/`  
**Target**: Four lazy-loaded modules — `student-ug`, `student-pg`, `admin`, `faculty` — each with its own `features/`, `routes/`, and entry point.

---

## Module Map (CampusPilot-Specific)

| Module | Programme Groups | Classroom Tabs | Main Sections (NavTabs) | Notes |
|--------|------------------|----------------|-------------------------|-------|
| **student-ug** | UG (BTech, BDes) | Live Schedule, Attendance, Vacant Rooms, Exam | Classroom, Events (My Team), Important, Feedback, Profile | Full toolkit |
| **student-pg** | PG (MTech, MDes), PHD | Live Schedule, Exam | Classroom, Events (My Team), Important, Feedback, Profile | No Attendance, no Vacant Rooms |
| **admin** | — | — | Feedback Responses, Web Monitoring, Android Monitoring, Profile | Separate shell |
| **faculty** | — | — | (placeholder) | Future work |

> **Key invariant**: `GROUP_CLASSROOM_TABS` in `shared/constants.ts` is the single source of truth for which classroom tabs each programme group sees. Modules must import and respect it.

---

## Phase 0 — Baseline (30 min)

**Goal**: Freeze current working state.

| Task | Verify |
|------|--------|
| `git commit -am "baseline before modules"` | Clean history point |
| `npx tsc --noEmit && npx eslint src --ext .ts,.tsx && npx vitest run` | All green |
| `npx vite build` | Production build works |
| Manual: register UG → see 4 classroom tabs; register PG → see 2 classroom tabs | Current gating works |

---

## Phase 1 — Harden `src/shared/` (2–3 hrs)

**Goal**: Pure shared layer with **zero** feature imports. Everything in `shared/` must be usable by any module without pulling in feature code.

| Task | Verify |
|------|--------|
| Audit `src/shared/` imports: `grep -r "from.*features" src/shared` → empty | No feature imports in shared |
| Confirm these are already in `shared/` (do **not** move):<br>• `api.ts` (re-exports from `shared/lib/*` and `shared/types/api.ts`)<br>• `AuthWrapper` + all auth screens → **move to `shared/auth/`**<br>• `useProfile`, `useProfileVersion`, `useProfileCourses`, `useLiveDay`<br>• `Spinner`, `ErrorBanner`, `NavIcons`, `FileUpload`, `UploadPreview`, `StatusCard`<br>• `types/api.ts`, `constants.ts`<br>• `lib/storage.ts`, `lib/time.ts`, `lib/sync.ts`, `lib/passkey.ts`, `lib/normalise.ts` | `tsc` passes |
| Create `src/shared/auth/` and move all auth components there (AuthWrapper, LoginForm, Signup*, VerifyEmail, Passkey*, PasswordReset, AdminLogin, StartScreen) | `tsc` passes |
| Delete any feature-specific code accidentally in `shared/` | Manual review |
| Add Vite alias `@shared` → `src/shared` in `vite.config.ts` | Import `@shared/...` works |
| Test: `npm test` (existing vitest) | All pass |

> **Why move AuthWrapper to shared?** It is the **session owner** — every module needs it, and it must not live inside a feature. Keeping it in `shared/auth/` makes the dependency direction explicit: modules → shared, never shared → modules.

---

## Phase 2 — Create Module Scaffolding (1 hr)

**Goal**: Empty module structure + Vite multi-entry config.

| Task | Verify |
|------|--------|
| `mkdir -p src/modules/{student-ug,student-pg,admin,faculty}/{features,routes}` | Tree exists |
| `vite.config.ts` → `build.rollupOptions.input` with 4 entries:<br>`student-ug: 'src/modules/student-ug/main.tsx'`<br>`student-pg: 'src/modules/student-pg/main.tsx'`<br>`admin: 'src/modules/admin/main.tsx'`<br>`faculty: 'src/modules/faculty/main.tsx'` | `npx vite build` → 4 `dist/module-*.js` |
| `src/core/App.tsx` (new) → dynamic `import()` by `programme_group` / `role` | Type-check passes |
| Update `main.tsx` → render `<App />` (unchanged) | Dev server loads |
| Smoke: `npm run dev` → login as UG → loads; login as PG → loads; login as admin → loads | No console errors |

**New `src/core/App.tsx` sketch**:
```tsx
import { useAuth } from '@shared/auth/AuthWrapper';
import { programmeGroupOf } from '@shared/constants';

export default function App() {
  const { user } = useAuth();
  const group = programmeGroupOf(user?.programme);

  if ((user?.role || 'student') === 'admin') {
    const AdminModule = await import('@modules/admin/main');
    return <AdminModule.default />;
  }
  if (group === 'UG') {
    const UGModule = await import('@modules/student-ug/main');
    return <UGModule.default />;
  }
  // PG + PHD
  const PGModule = await import('@modules/student-pg/main');
  return <PGModule.default />;
}
```

---

## Phase 3 — Migrate Student-UG Module (3–4 hrs)

**Goal**: Full UG feature parity in its own module.

| Task | Verify |
|------|--------|
| Copy `features/schedule/LiveSchedule.tsx` → `modules/student-ug/features/schedule/` | File exists |
| Copy `features/attendance/Attendance.tsx` → `modules/student-ug/features/attendance/` | |
| Copy `features/rooms/VacantRoomLookup.tsx` → `modules/student-ug/features/rooms/` | |
| Copy `features/exams/ExamSeating.tsx` → `modules/student-ug/features/exams/` | |
| Copy `features/teams/` (Teams, TeamDetail, TeamCard, MatchScore, Hackathons, CreateTeam) → `modules/student-ug/features/teams/` | |
| Copy `features/feedback/Feedback.tsx` → `modules/student-ug/features/feedback/` | |
| Copy `features/profile/Profile.tsx` → `modules/student-ug/features/profile/` | |
| Copy `features/classroom/` → **delete** (duplicates of schedule/attendance/rooms/exams) | No `classroom/` in module |
| Copy `features/myteam/` → **delete** (duplicates of teams/) | No `myteam/` in module |
| Update all imports: `../../../shared` → `@shared` (alias) | `tsc` passes |
| Create `modules/student-ug/routes.tsx` defining all 4 classroom tabs + Events (MyTeam) + Feedback + Profile | Manual: every tab renders |
| Create `modules/student-ug/main.tsx` mounting `<StudentUGRoutes />` | Dev server loads |
| Unit tests: copy/adapt vitest specs to module location | `vitest run` → all pass |
| Integration smoke: register new UG → full flow → every feature works | Checklist: LiveSchedule, Attendance, VacantRooms, Exams, Teams, Feedback, Profile |

---

## Phase 4 — Migrate Student-PG Module (2–3 hrs)

**Goal**: PG feature set (subset of UG) in its own module.

| Task | Verify |
|------|--------|
| Copy only `LiveSchedule`, `ExamSeating`, `Teams`, `Feedback`, `Profile` → `modules/student-pg/features/` | No Attendance, no VacantRooms |
| `modules/student-pg/routes.tsx` → Classroom tabs = `['live', 'exam']` only (via `GROUP_CLASSROOM_TABS.PG`) | Manual: PG login → only 2 classroom tabs |
| Reuse `Profile` component from `student-ug/features/profile` (import via `@modules/student-ug/features/profile` or move to `shared/features/profile` if shared) | Profile edits work, programme-aware branches |
| Unit tests: PG-specific specs (no attendance/vacant tests) | `vitest run` passes |
| Smoke: register PG → full flow → only PG features visible | Checklist |

> **Decision**: Keep `Profile` in `student-ug` and import it, or move to `shared/features/profile`? Since Profile is identical for all students, **move to `shared/features/profile`** in Phase 1.5 (quick sub-task).

---

## Phase 5 — Migrate Admin Module (1–2 hrs)

**Goal**: Admin panels isolated.

| Task | Verify |
|------|--------|
| Move `features/admin/` (AdminPanel, AdminLogin, ReinforcementPatterns) → `modules/admin/features/admin/` | |
| Move `features/monitoring/` → `modules/admin/features/monitoring/` | |
| `modules/admin/routes.tsx` → Feedback Responses, Web Monitoring, Android Monitoring, Profile | |
| `modules/admin/main.tsx` → mounts `<AdminRoutes />` | |
| Smoke: login as admin → only admin UI | No student tabs leak |

---

## Phase 6 — Faculty Module Skeleton (1 hr)

**Goal**: Empty module ready for future work.

| Task | Verify |
|------|--------|
| `modules/faculty/features/` (empty), `routes.tsx` (placeholder), `main.tsx` | Loads without error |
| `App.tsx` → `role === 'faculty'` → loads faculty module | Manual: future-proof |

---

## Phase 7 — Delete Old `features/` + Cleanup (1 hr)

**Goal**: No dead code left in root `features/`.

| Task | Verify |
|------|--------|
| `rm -rf src/features` (after verifying all imports point to `modules/` or `shared/`) | `tsc`, `eslint`, `vitest` all green |
| `vite build` → 4 modules, sizes approx:<br>UG ~350 KB, PG ~180 KB, Admin ~100 KB, Faculty ~50 KB | Module sizes as expected |
| Full regression: register UG, PG, admin → complete flows | Checklist per role |

---

## Phase 8 — Hardening (1–2 hrs)

**Goal**: Production confidence.

| Task | Verify |
|------|--------|
| E2E tests (Playwright) for each module's critical path | CI green |
| Module size budgets in `vite.config.ts` (`chunkSizeWarningLimit`) | Build fails if modules bloat |
| Error boundaries per module (wrap each module's root) | Manual: throw in one module → others unaffected |
| Docs: `MODULE_ARCHITECTURE.md` in repo | Team can onboard |

---

## Phase Gates (Definition of Done per Phase)

| Gate | Command |
|------|---------|
| TypeScript | `npx tsc --noEmit` |
| Lint | `npx eslint src --ext .ts,.tsx` |
| Unit | `npx vitest run` |
| Build | `npx vite build` |
| Smoke | Manual checklist (see above) |
| Commit | `git add -A && git commit -m "phase N: ..."` |

---

## Risk Mitigation (CampusPilot-Specific)

| Risk | Mitigation |
|------|------------|
| Import path breakage | Use `@shared/*` and `@modules/*` Vite aliases from Phase 1 |
| Shared component drift | Keep `shared/` PR-reviewed; no feature code allowed |
| Auth state loss on module switch | `AuthWrapper` stays in `shared/auth/` — single session |
| `GROUP_CLASSROOM_TABS` drift | Single source in `shared/constants.ts`; modules import it |
| Duplicate `classroom/` & `myteam/` folders | **Delete them in Phase 3** — they are stale copies |
| Regression in Phase 7 | Run full smoke checklist before deleting `src/features` |
| Admin monitoring panels need server subsections list | `monitoringApi.subsections()` already returns server-owned list — no local copy to sync |

---

## Timeline Estimate

| Phase | Hours | Cumulative |
|-------|-------|------------|
| 0 | 0.5 | 0.5 |
| 1 | 2–3 | 3 |
| 2 | 1 | 4 |
| 3 | 3–4 | 7–8 |
| 4 | 2–3 | 9–11 |
| 5 | 1–2 | 10–13 |
| 6 | 1 | 11–14 |
| 7 | 1 | 12–15 |
| 8 | 1–2 | **13–17 hrs** |

---

## Quick Reference: Current Feature Inventory

```
src/features/
├── auth/              → MOVE to shared/auth/ (Phase 1)
├── schedule/          → UG only (LiveSchedule)
├── attendance/        → UG only
├── rooms/             → UG only (VacantRoomLookup)
├── exams/             → UG + PG (ExamSeating)
├── teams/             → UG + PG (Teams, Hackathons, CreateTeam, etc.)
├── profile/           → ALL students (MOVE to shared/features/profile/)
├── feedback/          → ALL students
├── admin/             → Admin only (AdminPanel, ReinforcementPatterns)
├── monitoring/        → Admin only (Monitoring + 6 panels)
├── classroom/         → DUPLICATE (delete in Phase 3)
└── myteam/            → DUPLICATE (delete in Phase 3)
```

---

## Vite Aliases to Add (Phase 1)

```ts
// vite.config.ts
resolve: {
  alias: {
    '@': path.resolve(__dirname, './src'),
    '@shared': path.resolve(__dirname, './src/shared'),
    '@modules': path.resolve(__dirname, './src/modules'),
  },
},
```

---

## Notes for the Team

1. **AuthWrapper is the session gatekeeper** — it must stay in `shared/auth/` and wrap the *entire* app (as it does today). Modules receive the authenticated user via context.
2. **ProfileProvider** wraps the student shell — keep it in `shared/hooks/useProfile.tsx`. Modules consume `useProfile()`.
3. **NavTabs & Icons** are in `shared/components/NavIcons.tsx` and `shared/constants.ts` — modules import `NAV_TABS`, `SECTION_LABELS`, `SECTION_ICONS`.
4. **Programme group logic** lives in `shared/constants.ts` (`programmeGroupOf`, `GROUP_CLASSROOM_TABS`). Modules **import** these, never duplicate.
5. **AdminLogin** moves to `shared/auth/` (used by AuthWrapper) but the admin *shell* lives in `modules/admin/`.
6. **Monitoring panels** (Health, Activity, Feedback, Security, Monetisation, History) stay together in `modules/admin/features/monitoring/panels/`.
7. **No faculty backend yet** — Phase 6 is purely a placeholder so the module loader doesn't crash.