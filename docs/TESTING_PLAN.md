# CampusPilot Monitoring - Testing & Maintenance Plan

---
## 1. Test Strategy Overview

| Layer | Tool | Coverage | Frequency |
|-------|------|----------|-----------|
| Unit | pytest | 784 tests (all backend) | Every PR + CI |
| Integration | pytest + TestClient | Collector → DB → Rollup → Queries | Every PR |
| E2E | Playwright | Admin panel flows | Nightly |
| Contract | Promptfoo | 8 LLM prompts + schemas | Every PR |
| Chaos | Custom scripts | Infra failure injection | Quarterly |
| Security | Trivy/Gitleaks/Semgrep | Supply chain + SAST + secrets | Every PR + Daily |

---
## 2. Test Inventory

### 2.1 Unit Tests (784 tests, 9 skipped)

| Module | Tests | Key Coverage |
|--------|-------|--------------|
| `test_monitoring.py` | 126 | Collector, queries, rollup, admin routes, scans |
| `test_auth.py` | ~30 | Signup, login, OTP, passkeys, rate limits |
| `test_signup_verification.py` | ~20 | Email verification flow |
| `test_password_reset.py` | ~15 | Reset codes, token validation |
| Other | ~600 | Core features (timetable, exams, teams, etc.) |

**Monitoring-specific test classes (126 tests):**
- `TestCollectorRoutes` (10) - ingestion, rate limits, IP hashing
- `TestAdminRoutes` (13) - overview, history, rollup, scan endpoints
- `TestRollup` (10) - hourly rollup, idempotency, pruning
- `TestRollupSql` (7) - compiled SQL assertions (PG + SQLite)
- `TestUserMetrics` (6) - active_users, sessions_count, new_vs_returning
- `TestRetention` (9) - cohort alignment, calendar days
- `TestFunnel` (3) - drop-off %, negative = growth
- `TestDimensions` (3) - allowlist, unknown rendering
- `TestSecurityCounts` (2) - grouped by kind, kind filter
- `TestCrashes` (4) - crash-free rate, clusters
- `TestRevenueAndAds` (5) - verified/unverified, ARPU, eCPM, CTR
- `TestWindows` (2) - previous_window, baseline_window
- `TestPseudonymisation` (3) - HMAC determinism, length, pepper
- `TestRateLimiter` (5) - sliding window behavior

### 2.2 Integration Tests (Target: 100% pipeline coverage)

| Pipeline | Test | Status |
|----------|------|--------|
| Collector → DB → Rollup → Queries | `tests/test_monitoring.py::TestRollup` | ✅ |
| Scan worker → Stage 1 → Stage 2 LLM → Reconciliation → Storage | `scan_service.run_stage2_scan` | 🔄 (needs test) |
| Alert pipeline: Prometheus → Alertmanager → Apprise → Telegram | Manual verify | 🔄 |
| Rollup worker → hourly → prune → query consistency | `rollup.py --loop` | ✅ (smoke) |

### 2.3 E2E Tests (Playwright)

| Flow | Status | Selectors |
|------|--------|-----------|
| Admin login → monitoring tabs | 🔄 | `.monitoring-tab` |
| Date range → scan trigger → result view | 🔄 | `button:has-text("Scan now")` |
| History tab → date range → compare → export CSV | 🔄 | `button:has-text("Export")` |
| Scan history → incident log → tool call audit | 🔄 | `[data-testid="tool-calls"]` |
| Feedback panel → sentiment → topics | ✅ | `.sentiment-bar`, `.topic-list` |

---
## 3. Promptfoo Evaluation Suite (Phase 7)

### 3.1 Configuration

```yaml
# prompts/eval.yaml
providers:
  - id: ollama:qwen3:8b
    config:
      baseURL: http://localhost:11434/v1

prompts:
  - file: prompts/scan-web-health.txt
  - file: prompts/scan-web-activity.txt
  - file: prompts/scan-web-security.txt
  - file: prompts/scan-web-feedback.txt
  - file: prompts/scan-android-health.txt
  - file: prompts/scan-android-activity.txt
  - file: prompts/scan-android-security.txt
  - file: prompts/scan-android-feedback.txt

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

### 3.2 Test Cases per Subsection

| Subsection | Golden Window | Expected Status | Key Assertions |
|------------|---------------|-----------------|----------------|
| A_W_HEALTH | Normal ops | healthy | p95 < 500ms, 5xx < 0.5% |
| A_W_HEALTH | High latency | warning | p95 500ms-2s |
| A_W_HEALTH | Outage | critical | p95 > 2s, 5xx > 5% |
| B_W_ACTIVITY | Normal growth | healthy | DAU change ±15% |
| B_W_ACTIVITY | DAU drop 40% | critical | DAU drop > 40% |
| C_W_SECURITY | Brute force | critical | failed logins > 1000/h |
| D_W_FEEDBACK | Negative spike | warning | sentiment < 0.3 |
| A_A_HEALTH | Crash-free 99.2% | warning | 99.0-99.5% |
| C_A_SECURITY | Root signal 3% | warning | root > 2% |
| D_A_FEEDBACK | Crash correlation | critical | ≥ 10 complaints |

### 3.3 Reconciliation Test

```python
# tests/test_reconciliation.py
def test_reconciliation_catches_hallucination():
    """A model that invents a p99 should fail reconciliation."""
    from features.monitoring.scan_service import _reconcile_findings
    from features.monitoring.schemas import ScanResult, Finding, Metric
    
    # Craft a result with a fabricated metric
    fake_result = ScanResult(
        status="healthy",
        findings=[Finding(
            title="Fake latency",
            severity="info",
            evidence=[Metric(
                metric="http_request_duration_seconds_p99",
                value=999.0,  # Fabricated
                unit="s",
                previous_value=0.5,
                change_pct=199700,
                window="5m",
                source="promql"
            )]
        )],
        # ... other fields
    )
    
    # Reconciliation should fail because 999.0 != actual p99
    with pytest.raises(ScanInvalid):
        _reconcile_findings(db, fake_result, start, end, "web")
```

---
## 4. CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: campuspilot
          POSTGRES_PASSWORD: campuspilot
          POSTGRES_DB: campuspilot
        ports: [5432:5432]
        options: >-
          --health-cmd "pg_isready"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 20
    
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - name: Install deps
        run: pip install -r backend/requirements.txt
      - name: Run tests
        run: |
          cd backend/backend
          python -m pytest tests/ --tb=no -q
        env:
          DATABASE_URL: postgresql+psycopg://campuspilot:campuspilot@localhost:5432/campuspilot
          TELEMETRY_ENABLED: "true"
          TELEMETRY_PEPPER: "test-pepper"
          SCAN_ENABLED: "false"

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Trivy scan
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: fs
          severity: HIGH,CRITICAL
          exit-code: 1
      - name: Gitleaks
        uses: gitleaks/gitleaks-action@v2
      - name: Semgrep
        uses: returntocorp/semgrep-action@v1
      - name: Gitleaks (repo)
        run: gitleaks detect --source .

  promptfoo:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - run: npx promptfoo eval -c prompts/eval.yaml
        env:
          OLLAMA_BASE_URL: http://localhost:11434/v1
```

---
## 4. Maintenance Schedule

| Frequency | Task | Owner | Artifact |
|-----------|------|-------|----------|
| **Every PR** | Unit tests + security scans | CI | Green check |
| **Daily** | Promptfoo regression | CI | Report |
| **Weekly** | Dependency updates (Dependabot) | Bot | PR |
| **Weekly** | Rollup lag check | Cron | Alert |
| **Monthly** | Promptfoo full eval | CI | Report |
| **Monthly** | Backup restore test | Ops | Log |
| **Quarterly** | Chaos engineering drill | Ops | Runbook |
| **Quarterly** | Chaos: kill backend/postgres/ollama | Ops | Incident sim |
| **Quarterly** | Promptfoo full regression | CI | Report |
| **Semi-annual** | Security audit (OWASP ASVS) | Sec | Checklist |
| **Annual** | DPDP compliance review | Legal | Report |
| **Annual** | License audit (FOSSA/license-checker) | Eng | Report |

---
## 5. Rollback & Recovery Procedures

| Scenario | Detection | Response | RTO | RPO |
|----------|-----------|----------|-----|-----|
| Backend crash | `ApiDown` alert | Auto-restart (docker) | < 30s | 0 |
| Postgres crash | `DatabaseUnreachable` | WAL replay + restart | < 5m | < 1m |
| Ollama OOM | Scan status = error | Fallback to Stage 1 | < 1m | 0 |
| Disk full | `HostDiskWillFillSoon` | Alert + manual cleanup | < 30m | 0 |
| Prometheus OOM | `PrometheusDown` | Restart + reduce retention | < 5m | 0 |
| Scan worker deadlock | Queue depth > 10 | Kill + restart worker | < 2m | 0 |
| LLM hallucination | Reconciliation fail | Retry at lower temp → error | < 5m | 0 |

**Backup Schedule:**
- **Continuous:** WAL streaming to S3-compatible
- **Daily 03:00:** `pg_dump --format=custom` → encrypted → S3
- **Weekly:** Full cluster backup + schema dump
- **Retention:** Daily 30d, Weekly 12w, Monthly 12m

**Restore Procedure:**
```bash
# 1. Stop backend
docker compose stop backend

# 2. Restore from latest daily
pg_restore -d campuspilot latest.dump

# 3. Replay WAL to point-in-time
pg_waldump --start=... --end=... | psql campuspilot

# 4. Verify counts
python -m tools/verify_postgres.py

# 5. Restart
docker compose up -d backend
```

---
## 6. Monitoring the Monitor

| Metric | Alert Threshold | Action |
|--------|-----------------|--------|
| `up{job="campuspilot-api"}` == 0 | 2m | Page on-call |
| `absent(campuspilot_collector_events_total)` | 30m | Check collector |
| `prometheus_tsdb_head_samples_appended_total` rate drop | 5m | Check scrape targets |
| `campuspilot_rollup_lag_minutes` > 120 | 5m | Check rollup worker |
| `campuspilot_scan_queue_depth` > 10 | 5m | Scale worker |
| `ollama_up` == 0 | 5m | Restart ollama |
| `campuspilot_scan_status{status="error"}` > 0 | 1m | Check scan logs |

---
## 7. Documentation Maintenance

| Doc | Owner | Update Trigger |
|-----|-------|----------------|
| `ARCHITECTURE.md` | Eng | New service/major change |
| `API.md` | Eng | New endpoint/param change |
| `SCHEMA.md` | Eng | Migration |
| `PROMPTS.md` | Eng | Prompt change |
| `TESTING_PLAN.md` | QA | New test type |
| `SECURITY_CHECKLIST.md` | Sec | Quarterly review |
| `ROADMAP.md` | PM | Sprint planning |

---
## 8. Version Compatibility Matrix

| Component | Lite | Full | Notes |
|-----------|------|------|-------|
| Python | 3.11+ | 3.11+ | 3.10 min |
| PostgreSQL | 16 | 16 | Alpine |
| Prometheus | 2.54 | 2.54 | |
| Grafana | 11.1 | 11.1 | |
| Ollama | latest | latest | qwen3:4b / qwen3:30b-a3b |
| VictoriaLogs | - | 1.10 | Full only |
| Alertmanager | 0.27 | 0.27 | |
| Apprise (notify) | latest | latest | |

---
## 9. Known Limitations & Technical Debt

| Item | Severity | Mitigation |
|------|----------|------------|
| VADER sentiment English-only | Medium | Add Indic NLP later |
| Keyword topics (not BERTopic) | Low | Upgrade in full profile |
| No multi-replica rollup | Medium | `ROLLUP_INLINE=false` + rollup worker |
| SQLite test dialect diverges | Low | Dual-dialect CI catches it |
| No distributed tracing | Medium | Add OpenTelemetry later |
| No formal load testing | Medium | Add k6 scripts |

---
## 10. Sign-off

| Role | Name | Date | Status |
|------|------|------|--------|
| Engineering Lead | | | ☐ |
| QA Lead | | | ☐ |
| Security Lead | | | ☐ |
| DevOps | | | ☐ |

---
*Document version: 1.0 | Last updated: 2026-10-08 | Next review: 2026-11-08*