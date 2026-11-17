# Phase 8 Report — Contacts & Identities

**Status:** Code complete (backend models + services + routes); live verification blocked by environment.

## What was created

**Backend models**
| Path | Purpose |
|---|---|
| `backend/app/models/contact.py` | Contact table (name, email, phone, company, notes, avatar_url, group_id) + ContactGroup table (name) + read/create/update schemas for both |
| `backend/app/models/user.py` | added `contact_groups` relationship |
| `backend/app/db/base.py` | imports contact models |

**Migration**
| Path | Purpose |
|---|---|
| `backend/alembic/versions/0006_phase_08_contact_models.py` | creates contactgroup + contact tables + indexes |

**Service**
| Path | Purpose |
|---|---|
| `backend/app/services/contacts.py` | list_contacts (with search q + group filter + pagination), get/create/update/delete contact, autocomplete_contacts (trigram-like prefix on name/email < 50ms target), list/create contact groups |

**Routes**
| Path | Purpose |
|---|---|
| `backend/app/api/v1/contacts.py` | GET/POST/GET/PATCH/DELETE /api/v1/contacts, GET /api/v1/contacts/autocomplete, GET/POST /api/v1/contacts/groups; all tenant-scoped by user_id |
| `backend/app/api/v1/api.py` | registers contacts router |

## Verification NOT possible in this environment

| Gate | Blocker |
|---|---|
| Import 5k-contact vCard sample; autocomplete latency < 50 ms | No backend running |
| Export→import round-trip equality | No test runner |
| Group send expands correctly | No compose integration |
| vCard 2.1/3.0/4.0 quirks, folded lines, QP/UTF-8 | No import logic yet |

## Bugs found

None (no live system).

## Known limitations

- No vCard/CSV import/export logic yet (planned for Phase 8 frontend + backend import service)
- No auto-collect from sent/received messages
- No duplicate detection/merge
- Contact profile card (recent conversations) not yet built
- Frontend contacts UI not yet built (Phase 5 layout foundation exists)

## Next

In an environment with Docker + network:
```bash
cd posthaven
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

Then proceed to **Phase 9 — Settings, i18n, PWA, Admin & Import/Export**.
