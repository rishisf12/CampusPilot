# CampusPilot Monitoring - Phased Roadmap
# Zero-cost, self-hosted, OSI-licensed only

---
## Phase Summary

| Phase | Focus | Duration | Status |
|-------|-------|----------|--------|
| 0 | Foundation & Plan | 1 day | ✅ Done |
| 1 | Schema + Collectors + Read-Only Role | 2 days | ✅ Done |
| 2 | Rule Engine + Scan Service + Auth Hardening | 3 days | ✅ Done |
| 3 | Analytics/Monetization + Android SDK | 2 days | ✅ Done |
| 4 | Android Health + Security Scans | 2 days | ✅ Done |
| 5 | Feedback NLP Pipeline | 1 day | ✅ Done |
| 6 | History Dashboard | 2 days | ✅ Done |
| 7 | Stage 2 LLM (Ollama) | 3 days | ✅ Done |
| 8 | Alerting + Profiles + Hardening + Docs | 3 days | 🔄 In Progress |

**Total: ~19 days** (completed: 16 days)

---
## Phase 8 Detail: Alerting + Profiles + Hardening + Docs

### Week 1: Alerting & Notification Stack (3 days)

| Task | Description | Effort | Dependencies |
|------|-------------|--------|--------------|
| 8.1 | Alertmanager config + routing | 4h | Prometheus |
| 8.2 | Prometheus alert rules (27 rules) | 6h | Phase 1-7 metrics |
| 8.3 | Apprise notification service (Telegram/Webhook/Email) | 4h | Docker |
| 8.3b | Alert routing by severity/subsection | 2h | Alertmanager |
| 8.4 | Test notifications end-to-end | 2h | Telegram bot |

**Deliverables:**
- `ops/alertmanager/alertmanager.yml`
- `ops/prometheus/alerts.yml` (27 rules across 8 subsections)
- `ops/alerting/README.md` (Apprise config guide)
- Verified Telegram alerts firing

### Week 2: Docker Profiles + Hardening (3 days)

| Task | Description | Effort | Dependencies |
|------|-------------|--------|--------------|
| 8.5 | Docker Compose `lite` profile (4 GB) | 4h | Phase 1-7 |
| 8.6 | Docker Compose `full` profile (16 GB) | 4h | 8.1-8.3 |
| 8.7 | Resource limits + reservations per service | 3h | docker-compose.yml |
| 8.7b | PostgreSQL tuning per profile | 2h | postgres config |
| 8.8 | Security hardening | 6h | Phase 1-7 |
| 8.8b | Read-only role enforcement | 2h | Phase 1 |
| 8.8c | Tool allowlist enforcement | 2h | Phase 7 |
| 8.8d | Network isolation (internal network) | 2h | docker-compose.yml |
| 8.8e | Supply chain hardening (Trivy/Gitleaks/Semgrep in CI) | 4h | GitHub Actions |

**Deliverables:**
- Updated `docker-compose.yml` with `lite`/`full` profiles
- Resource limits per service
- `SECURITY_CHECKLIST.md` (comprehensive)
- CI pipeline with Trivy/Gitleaks/Semgrep

### Week 3: Documentation + Testing Plan (3 days)

| Task | Description | Effort | Dependencies |
|------|-------------|--------|--------------|
| 8.9 | Architecture diagram (Mermaid) | 4h | All phases |
| 8.10 | Admin wireframes (Figma/Excalidraw) | 4h | Phase 3-6 UI |
| 8.11 | Database schema doc | 3h | Phase 1 models |
| 8.12 | REST API examples (OpenAPI/Swagger) | 4h | Phase 2 routes |
| 8.13 | 8 scan prompts + JSON schemas | 4h | Phase 7 |
| 8.14 | opencode.json + tool allowlists | 2h | Phase 7 |
| 8.15 | Testing plan + Promptfoo evals | 6h | Phase 7 |
| 8.16 | Security & privacy checklist | 4h | All phases |
| 8.17 | Phased roadmap (this doc) | 2h | This doc |

**Deliverables:**
- `docs/ARCHITECTURE.md` (Mermaid diagram)
- `docs/WIREFRAMES.md` (admin panel screens)
- `docs/SCHEMA.md` (SQL + descriptions)
- `docs/API.md` (endpoint docs + examples)
- `docs/PROMPTS.md` (8 prompts + JSON schemas)
- `docs/opencode.json` (project config)
- `docs/TESTING_PLAN.md` (unit/integration/e2e + Promptfoo)
- `SECURITY_CHECKLIST.md`

---
## Phase 8 Resource Estimates

### Hardware (VPS) Sizing

| Profile | RAM | vCPU | Disk | Monthly Cost (est.) |
|---------|-----|------|------|---------------------|
| **Lite** | 4 GB | 2 | 40 GB | $4-6 (Hetzner/DO) |
| **Full** | 16 GB | 6 | 160 GB | $16-24 (Hetzner/DO) |

**PostgreSQL Tuning per Profile:**

| Param | Lite (4 GB) | Full (16 GB) |
|-------|-------------|--------------|
| `shared_buffers` | 256 MB | 2 GB |
| `work_mem` | 8 MB | 32 MB |
| `maintenance_work_mem` | 64 MB | 256 MB |
| `effective_cache_size` | 1 GB | 10 GB |
| `max_connections` | 100 | 200 |

### Service RAM Budgets (Full Profile)

| Service | RAM Limit | Notes |
|---------|-----------|-------|
| postgres | 2 GB | Primary DB |
| backend | 2 GB | API + scan worker |
| frontend | 512 MB | nginx + React |
| prometheus | 1 GB | 15d retention |
| victoria-logs | 4 GB | 30d logs |
| grafana | 1 GB | Dashboards |
| ollama | 10 GB | qwen3:30b-a3b (~18 GB disk) |
| alertmanager | 256 MB | |
| alerting (Apprise) | 256 MB | |
| cAdvisor | 1 GB | Container metrics |
| blackbox-exporter | 256 MB | Synthetic checks |
| ollama | 10 GB | qwen3:30b-a3b |
| **Total** | **~22 GB** | Fits 16 GB with swap |

**Lite Profile (4 GB) - drop:**
- victoria-logs → remove
- Grafana → remove
- cAdvisor → remove
- blackbox-exporter → remove
- ollama → qwen3:4b (2 GB)
- **Total: ~3.5 GB** ✅

---
## Testing Strategy

### Unit Tests (Existing - 784 passing)
- [x] Collector validation, rate limiting, IP hashing
- [x] Query functions (retention, funnel, top_dimensions, etc.)
- [x] Rollup idempotency, pruning
- [x] Admin endpoints (overview, health, history, scan)
- [x] Auth flows (signup, login, OTP, passkeys)

### Integration Tests (Target: 100% coverage)
- [ ] **Collector → DB → Rollup → Queries** full pipeline
- [ ] **Scan worker** → Stage 1 → Stage 2 LLM → Reconciliation → Storage
- [ ] **Alert pipeline** → Prometheus → Alertmanager → Apprise → Telegram
- [ ] **Rollup worker** → hourly → prune → query consistency

### E2E Tests (Playwright)
- [ ] Admin panel login → monitoring tabs → scan trigger → result view
- [ ] History tab → date range → compare → export CSV
- [ ] Scan history → incident log → tool call audit
- [ ] Feedback panel → sentiment → topics

### Promptfoo Evaluation Suite (Phase 7)
```yaml
# prompts/eval.yaml
providers:
  - id: ollama:qwen3:8b
    config:
      baseURL: http://localhost:11434/v1

prompts:
  - file: prompts/scan-web-health.txt
  - file: prompts/scan-web-activity.txt
  # ... all 8

tests:
  - vars:
      subsection: A_W_HEALTH
      window_days: 7
    assert:
      - type: json-schema
        schema: schemas/ScanResult.json
      - type: contains
        value: "healthy"
      - type: not-contains
        value: "hallucinated"
      - type: python
        code: |
          # Reconciliation check
          for finding in output.findings:
            for ev in finding.evidence:
              assert reconcile(ev.metric, ev.value) < 0.02
```

**Promptfoo CI:** Runs on every PR, fails if regression detected.

### Chaos Engineering (Quarterly)
- [ ] Kill backend pod → verify auto-restart + no data loss
- [ ] Kill postgres → verify WAL replay + connection retry
- [ ] Kill ollama → scan falls back to Stage 1 only
- [ ] Fill disk → verify `HostDiskWillFillSoon` alert
- [ ] Kill network → verify graceful degradation

---
## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Ollama model hallucination | Medium | High | Reconciliation pass (2%), Stage 1 authoritative |
| Prompt injection in feedback | Medium | High | `<untrusted-data>` wrapping, tool allowlists |
| Ollama OOM on 4 GB box | High | High | `keep_alive=0`, qwen3:4b fallback |
| Prometheus OOM on 4 GB | Medium | High | Retention 15d, size 2GB, drop cadvisor |
| Alert fatigue | Medium | Medium | Only 27 rules, severity-based routing |
| Data breach via monitoring | Low | Critical | Read-only role, HMAC pseudonymization, no raw PII |
| Scan worker deadlock | Low | Medium | Concurrency=1, timeout=240s, 1 retry |
| Prompt injection in LLM | Medium | High | Tool allowlists, closed action enum, reconciliation |
| Supply chain compromise | Low | Critical | Trivy/Gitleaks/Semgrep in CI, pinned images |

---
## Go/No-Go Criteria for Phase 8 Completion

| Criterion | Target | Status |
|-----------|--------|--------|
| All 784 tests pass | 784/784 | ✅ |
| 126 monitoring tests pass | 126/126 | ✅ |
| Alertmanager routes fire correctly | Manual verify | 🔄 |
| Telegram alerts received | Manual verify | 🔄 |
| Lite profile starts on 4 GB | `docker compose --profile lite up` | 🔄 |
| Full profile starts on 16 GB | `docker compose --profile full up` | 🔄 |
| Security checklist ≥ 90% | ≥ 90% | 🔄 |
| Promptfoo evals pass | 8/8 prompts | 🔄 |
| Documentation complete | All 8 docs | 🔄 |

---
## Timeline

```
Week 1 (Oct 8-12):  Alerting stack + Prometheus rules + Apprise
Week 2 (Oct 15-19): Docker profiles + hardening + CI hardening
Week 3 (Oct 22-26): Documentation + testing plan + Promptfoo evals
Buffer (Oct 29-Nov 2): Buffer for integration issues
```

**Target completion: Nov 2, 2026**

---
## Post-Launch (Phase 9+)

| Phase | Focus | Timeline |
|-------|-------|----------|
| 9 | Android SDK distribution + Play Console | Q1 2027 |
| 10 | Web beacon (JS SDK) + CDN | Q1 2027 |
| 11 | Multi-tenant (other campuses) | Q2 2027 |
| 12 | ML-based anomaly detection (local) | Q3 2027 |

---
*Roadmap version: 1.0 | Last updated: 2026-10-08 | Next review: 2026-11-02*