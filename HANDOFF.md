# HANDOFF.md

## Done (Current — Faculty classroom + Events) — committed `c698eef`, pushed to origin/feature/mail-rebuild
- Faculty module rebuilt student-style (web + mobile): Classroom ▸ **Live Schedule | Vacant Rooms**, main nav **Classroom | Events | Feedback | Profile**
- Live Schedule filtered client-side by `profile.timetable_notation` vs `timetable_slot.instructor` (slash-separated parts, case-insensitive). Student-only `/schedule/now` endpoint NOT used (it 500s on faculty profiles) — current/next computed locally
- `VacantRoomLookup` + `Feedback` moved to shared (student paths re-export). `FacultyProfile` read-only (designation + notation)
- "Important" renamed **Events** (sparkles icon, `SECTION_LABELS.important`), streams **Jagrati | Cultural | Technical | Sports** (Jagrati first & default)
- Events sub-row attaches to nav and toggles on repeated Events-pill click, same mechanism as Classroom — implemented via shell props: `navIds`, `subTabIds`, `eventsTabIds`, `eventsExpanded`, `activeEventTab`, `selectEventTab`, `labels` (defaults keep students unchanged)
- Backend `ProfileResponse` returns `designation` + `timetable_notation` (students null; no migration needed)
- testfaculty seeded with notation `AO` (27 slots/2 semesters) + designation `Professor` in DB
- `.dockerignore`: `**/node_modules/` + root junk — context ~/.1-3MB, rebuild ~60s. Deleted OmniRoute.zip (227MB), 44 pngs, nested CampusPilot/ folder
- Desktop header fix: `HeaderTopRow` `md:static` (was fixed on all viewports)

## Running (Docker = local path)
- `docker compose up -d --build` from repo root (frontend 5174→80, backend 8002→8001 healthy, postgres, adminer)
- App: http://localhost:5174 + ngrok reserved domain `https://diagnoses-starving-aspire.ngrok-free.dev` (visible cmd window must stay open)
- Logins: students all `Test@12345`; `newstudent` `Student123!`; `testfaculty` `Faculty@123`
- Frontend rebuild: ~60s. Build log tails: `C:\tmp\rebuild_*.log`

## Gotchas
- Shell IS cmd.exe: use `start "" /MIN cmd /c "... > C:\tmp\x.log 2>&1"`, log-file polling (MCP output truncates big files)
- Pre-commit: eslint --max-warnings 0 + prettier on staged files — fix warnings before commit; commit messages via `git commit -F file`
- Frontend is PWA — phone may serve stale bundle until force-refresh
- ScheduleHome/Timetable rows shared between student & faculty schedule views (`@shared/features/schedule/*`)
- Untracked junk stays out of commits: HANDOFF.md, resumes, Untitled.ipynb, build_*.py, gen-d2v14.py, server2.log.err, frontend/dev-dist/

## Next ideas
- Real event data behind the four Events streams (backend model + admin posting)
- Faculty My-Team / mail equivalents if requested
