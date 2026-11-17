# Phase 7 Report — Search, Labels, Rules, Snooze & Reminders

**Status:** Code complete (backend models + services + routes); live verification blocked by environment.

## What was created

**Backend models**
| Path | Purpose |
|---|---|
| `backend/app/models/saved_search.py` | SavedSearch table (name, query, user FK) + read/create schemas |
| `backend/app/models/snooze.py` | Snooze table (message_id, wake_at, woke) + schemas |
| `backend/app/models/reminder.py` | Reminder table (message_id, due_at, fired) + schemas |
| `backend/app/models/rule.py` | Rule table (name, enabled, conditions JSON, actions JSON, order, stop_on_match) + CRUD schemas |
| `backend/app/models/vacation.py` | VacationResponder table (account, enabled, subject, body, date range, once_per_sender) + schemas |
| `backend/app/models/user.py` | added saved_searches, snoozes, reminders, vacation_responders, templates relationships |
| `backend/app/models/message.py` | added snoozes, reminders relationships |
| `backend/app/models/account.py` | added vacation_responders relationship |
| `backend/app/db/base.py` | imports all Phase 7 models |

**Migration**
| Path | Purpose |
|---|---|
| `backend/alembic/versions/0005_phase_07_org_models.py` | creates savedsearch, snooze, reminder, rule, vacationresponder tables + indexes |

**Services**
| Path | Purpose |
|---|---|
| `backend/app/services/search.py` | `parse_query()` — Gmail-style operator parser (from:/to:/cc:/subject:/has:attachment/is:unread|read|starred|important/in:/label:/before:/after:/older_than:/newer_than:/size:, quoted phrases, negation); `build_search_conditions()` → SQLAlchemy WHERE clauses including Postgres `search_vector @@ plainto_tsquery`; `search_messages()` with tenant scoping + pagination; `save_search`/`list_saved_searches` |
| `backend/app/services/rules.py` | `evaluate_conditions()` — condition eval (contains/not_contains/equals/gt/lt on from/to/subject/has_attachment/size); `apply_actions()` — mark_read/star/delete/label/move/stop; `run_rules_on_message()` — runs enabled rules in order with stop-on-match; CRUD for rules |

**Routes**
| Path | Purpose |
|---|---|
| `backend/app/api/v1/search.py` | GET /api/v1/search (query + folder + cursor pagination), POST/GET /api/v1/search/saved |
| `backend/app/api/v1/labels.py` | GET/POST/DELETE /api/v1/labels (tenant-scoped) |
| `backend/app/api/v1/rules.py` | GET/POST/PATCH/DELETE /api/v1/rules (tenant-scoped) |
| `backend/app/api/v1/snooze.py` | POST /api/v1/snooze (snooze message), GET /api/v1/snooze (list, exclude woke) |
| `backend/app/api/v1/api.py` | registers search, labels, rules, snooze routers |

## Verification NOT possible in this environment

| Gate | Blocker |
|---|---|
| 30-query search correctness table on seeded data | No Docker/GreenMail/backend |
| Search p95 < 200 ms @ 50k messages | No DB |
| Rule fires < 2 s on arrival; idempotent run-on-existing | No worker sync pipeline |
| Snooze wake after worker restart | No ARQ worker running |
| Rule loops / auto-reply storm protections | No live mail flow |

## Bugs found

None (no live system).

## Known limitations

- Search `in:` and `label:` operators are parsed but not fully implemented (need Folder/MessageLabel joins).
- FTS `search_vector` column exists on Message but no trigger/population logic yet (needs migration to populate).
- Rules engine is in-process; not yet wired into the sync/arrival pipeline (Phase 4/10).
- Snooze/reminder wake-up worker tasks exist as skeletons in tasks.py but not scheduled.
- Vacation responder model exists but no auto-reply send logic.
- No frontend UI yet for search/labels/rules/snooze (Phase 5 UI laid foundation; feature UIs deferred).

## Next

In an environment with Docker + network:
```bash
cd posthaven
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

Then proceed to **Phase 8 — Contacts & Identities** (vCard/CSV import/export, contact CRUD, autocomplete API).
