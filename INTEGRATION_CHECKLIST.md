# Verification Checklist

What was verified against the running stack (backend on **8001**, frontend on
**5173**), and how to re-run each check yourself.

Legend: ✅ verified · ⬜ not yet possible (needs a real PDF)

---

## 1. Stack boots

| # | Check | How | Result |
|---|---|---|---|
| 1.1 | Backend starts clean | `python -m uvicorn main:app --port 8001` | ✅ |
| 1.2 | Health responds | `curl http://127.0.0.1:8001/health` → `{"status":"ok"}` | ✅ |
| 1.3 | Tables auto-created on a fresh database | delete `database/classpilot.db`, boot, inspect `PRAGMA table_info` | ✅ |
| 1.4 | Old schema migrated in place | `exam_date` renamed to `seating_date`; `branch`/`semester`/`is_extra` added; existing users preserved | ✅ |
| 1.5 | Frontend builds | `npm run build` | ✅ 46 modules |
| 1.6 | Dev server on 5173 | `npm run dev` | ✅ |
| 1.7 | Proxy reaches 8001 | `curl http://localhost:5173/health` | ✅ |

## 2. Authentication

| # | Check | Result |
|---|---|---|
| 2.1 | Signup rejects non-`@iiitdmj.ac.in` domains (422) | ✅ |
| 2.2 | Signup rejects passwords under 8 characters (422) | ✅ |
| 2.3 | Duplicate email / username / roll rejected (400) | ✅ |
| 2.4 | Signup emails a 6-digit code | ✅ (SMTP stubbed in tests) |
| 2.5 | Wrong code → 400 `Invalid verification code` | ✅ |
| 2.6 | Code expires after 10 minutes | ✅ |
| 2.7 | Resend replaces the previous code | ✅ |
| 2.8 | Login blocked (403) until verified | ✅ |
| 2.9 | Login is an OAuth2 form, not JSON | ✅ |
| 2.10 | Token works on `/auth/me` | ✅ |
| 2.11 | Unauthenticated request → 401 | ✅ |
| 2.12 | Bad token → 401, session cleared | ✅ |
| 2.13 | Network error keeps the user signed in (offline dot) | ✅ |
| 2.14 | Verification screen resumes after tab close | ✅ pending-email in `localStorage` |
| 2.15 | Resend cooldown persists across reload | ✅ |

## 3. Profile and branch change

| # | Check | Result |
|---|---|---|
| 3.1 | Branch list is exactly `CSE A, CSE B, DS, ECE, ME, SM, PG, MDes` | ✅ no bare `CSE`, no duplicates |
| 3.2 | From/To dropdowns use the placeholder "Select branch" | ✅ |
| 3.3 | Branch Change block sits inside the Profile card | ✅ |
| 3.4 | "No branch change" checkbox sits beside the button | ✅ |
| 3.5 | Branch change records From → To | ✅ `CSE A -> ECE` |
| 3.6 | `original_branch` preserved across later changes | ✅ |
| 3.7 | Making a change auto-unticks "No branch change" | ✅ |
| 3.8 | Ticking the box clears the pending request | ✅ `No branch change recorded (cleared pending request for ECE)` |
| 3.9 | Unknown branch rejected (400) | ✅ |
| 3.10 | Same source and target rejected (400) | ✅ |
| 3.11 | Profile change bumps `profile_version` (2 → 3) | ✅ |
| 3.12 | Semester options follow the programme | ✅ MTech → I–IV |

## 4. Timetable

| # | Check | Result |
|---|---|---|
| 4.1 | CSV upload → slots inserted, zero warnings | ✅ 6 slots |
| 4.2 | Malformed rows reported as warnings, not fatal | ✅ 2 inserted, 2 warnings |
| 4.3 | Missing columns → 400 with a clear message | ✅ |
| 4.4 | Re-upload replaces previous slots | ✅ |
| 4.5 | `Clear All` handles an empty 204 response | ✅ no crash |
| 4.6 | `/timetable/slots` serialises times as `HH:MM` strings | ✅ regression test |
| 4.7 | `/timetable/options` reports discovered branches/semesters/courses | ✅ |
| 4.8 | Upload triggers attendance course sync | ✅ 5 courses |
| 4.9 | Latest selected file persists across reloads | ✅ |
| 4.10 | Real class-timetable PDF parses | ⬜ source PDF is 0 bytes |

## 5. Rooms and schedule

| # | Check | Result |
|---|---|---|
| 5.1 | `/rooms/vacant` live mode with no timetable → 200 | ✅ regression test (was a 500) |
| 5.2 | `/rooms/vacant` manual mode → 200 | ✅ |
| 5.3 | `/rooms/vacant` reports `has_timetable` | ✅ |
| 5.4 | Vacant/occupied split correct for a known slot | ✅ L-101 busy 09:00 Mon |
| 5.5 | Weekend / lunch / after-hours messaging | ✅ `Weekend - no regular classes` |
| 5.6 | `/schedule/now` → current + next + server time | ✅ regression test (was a 500) |
| 5.7 | Other classes in the same slot listed | ✅ |
| 5.8 | Course code shown once; `(CODE)` only when name differs | ✅ |

## 6. Attendance

| # | Check | Result |
|---|---|---|
| 6.1 | Subjects sync from the timetable | ✅ 3 for CSE A sem 5 |
| 6.2 | Other branches' subjects excluded | ✅ ME/SM filtered out |
| 6.3 | Daily banner shows live IST clock | ✅ `20:53:51 IST` |
| 6.4 | Classes-today and unmarked counts correct | ✅ `2 classes today / All marked` |
| 6.5 | At-risk list with "attend next N" | ✅ |
| 6.6 | Subject grid is 2-up mobile / 3-up desktop | ✅ |
| 6.7 | Colour thresholds vs target | ✅ |
| 6.8 | P/A disabled with tooltip "No class scheduled today" | ✅ faded + disabled |
| 6.9 | C always enabled | ✅ |
| 6.10 | Optimistic mark updates the UI immediately | ✅ |
| 6.11 | Toast with one-tap Undo | ✅ `CS5031 marked Present Undo` |
| 6.12 | Undo actually deletes the record | ✅ records back to `[]`, 0/0 |
| 6.13 | Calendar modal: prev/next, month grid | ✅ October 2026, 31 cells |
| 6.14 | Today highlighted with a ring | ✅ `ring-2 ring-primary-500` |
| 6.15 | Colour legend for present/absent/cancelled/not marked/extra | ✅ |
| 6.16 | Only past dates are editable | ✅ 3 editable, 28 disabled |
| 6.17 | History sub-tab lists records with course codes | ✅ |
| 6.18 | Target % editable and drives colouring | ✅ stored in `localStorage` |

## 7. Exam

| # | Check | Result |
|---|---|---|
| 7.1 | Seating index PDF parses | ✅ 705 rows, 0 unknown, 0 skipped |
| 7.2 | Mid-sem timetable PDF parses | ✅ 75 rows, 0 unknown |
| 7.3 | All dates resolved across table boundaries | ✅ |
| 7.4 | No impossible time slots (`22:30 → 12:30`) | ✅ |
| 7.5 | Hall codes not mistaken for course codes | ✅ `CR103` excluded |
| 7.6 | Rooms joined onto timetable rows | ✅ regression tests |
| 7.7 | Roll lookup returns date, room, course code, day, time | ✅ |
| 7.8 | Duplicate rooms collapsed | ✅ |
| 7.9 | Roll prefilled from the signed-in user | ✅ `23BCS125` |
| 7.10 | Results restored after refresh | ✅ `exam_last_lookup` |
| 7.11 | Rule reported per exam (2 = exact, 3 = estimated) | ✅ |
| 7.12 | Profile-narrowed results labelled | ✅ `Filtered to your profile` |
| 7.13 | Upload cards side by side while empty, stacked when populated | ✅ |
| 7.14 | Each card shows "Uploaded (N entries)" + red Remove | ✅ 75 / 705 |
| 7.15 | Remove asks for confirmation | ✅ |
| 7.16 | Semester/branch filters default to the profile | ✅ |
| 7.17 | "Synced with profile" badge | ✅ |
| 7.18 | Hidden-row hint | ✅ `7 rows hidden by these filters.` |
| 7.19 | Day-N grouping | ✅ `Day-1 Wednesday` |
| 7.20 | Seating preview 20 rows + Show All | ✅ 126 entries |
| 7.21 | Refetch on `profile_version` change | ✅ |
| 7.22 | Today badge on lookup cards | ✅ code path, no exam today in seed data |

## 8. Cross-cutting

| # | Check | Result |
|---|---|---|
| 8.1 | Header flush at the top (`top === 0`), sticky | ✅ |
| 8.2 | Margin/padding reset on html, body, #root | ✅ all `0px` |
| 8.3 | Title and favicon | ✅ `logo-icon.svg` |
| 8.4 | Exactly one header and one footer | ✅ |
| 8.5 | Header shows only name, Logout and the live dot | ✅ |
| 8.6 | Tabs do not wrap at desktop width | ✅ `whitespace-nowrap` |
| 8.7 | Full Tailwind 50–900 palette | ✅ in `index.html` |
| 8.8 | No unused exports | ✅ audited and removed |
| 8.9 | No unhandled promise rejections in the console | ✅ |
| 8.10 | Backend test suite green | ✅ 225 passed |

---

## 9. Feedback & Email Ingestion

| # | Check | Result |
|---|---|---|
| 9.1 | Web form submits text + optional file | ✅ |
| 9.2 | Subject field in web form | ✅ |
| 9.3 | Feedback list shows subject as title | ✅ |
| 9.4 | Click feedback → dropdown expands with details | ✅ |
| 9.5 | Attachment badge (📎) shown inline | ✅ |
| 9.6 | Admin replies appear inside dropdown | ✅ |
| 9.7 | POST /feedback/ingest accepts email webhook | ✅ |
| 9.8 | Email from known user → user_id linked | ✅ |
| 9.9 | Email from unknown sender → anonymous entry | ✅ |
| 9.10 | Attachments saved and filenames shown | ✅ |
| 9.11 | Multiple attachments → concatenated filenames | ✅ |
| 9.12 | IMAP poller script exists (`tools/imap_feedback_poller.py`) | ✅ |
| 9.13 | Systemd service + timer for production | ✅ |

---

## Outstanding

1. **Class timetable PDF is 0 bytes** in `Downloads` — re-download it. The whole
   pipeline is proven with the CSV fixture in `test_timetable_flow.py`, so only
   the file itself is missing. It gates checklist items 4.10 and the live-data
   behaviour of 5.4, 5.7 and 6.1.
2. **Attendance target is browser-local** — needs `GET`/`PUT /attendance/target`.
3. **Instructor column is empty** — the exam rows carry no instructor field.
4. **Exam profile filter is approximate** — branch and semester are inferred from
   the roll prefix and course code.