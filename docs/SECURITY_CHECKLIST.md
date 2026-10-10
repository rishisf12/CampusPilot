# CampusPilot Security & Privacy Checklist
# Based on DPDP Act (India), OWASP ASVS, and zero-cost security principles

---
## 1. Data Protection & Privacy (DPDP Act Compliance)

### 1.1 Consent & Data Minimization
- [ ] **Explicit consent** obtained before collecting any personal data
- [ ] **Purpose limitation** - data collected only for stated purposes
- [ ] **Data minimization** - only collect what's strictly necessary
- [ ] **Storage limitation** - retention policies defined and enforced
- [ ] **Right to access** - users can request their data
- [ ] **Right to erasure** - users can request deletion (GDPR Art. 17 / DPDP Sec. 12)
- [ ] **Right to portability** - data export in machine-readable format

### 1.2 Personal Data Handling
- [ ] **No raw emails/roll numbers in monitoring tables** - all pseudonymized via HMAC
- [ ] **IP addresses never stored** - only truncated HMAC (32 hex chars)
- [ ] **User IDs never in clear** - `user_hash` = HMAC-SHA256(pepper, user_id)
- [ ] **No free-text user content in analytics** - `props` is flat map of scalars
- [ ] **Feedback text treated as untrusted data** - wrapped in `<untrusted-data>` for LLM
- [ ] **Roll numbers & college emails = personal data** - never in logs/fixtures

### 1.3 Consent Records
- [ ] Consent timestamp stored with each feedback submission
- [ ] Consent version tracked for policy updates
- [ ] Withdrawal mechanism available in app settings

---
## 2. Authentication & Authorization

### 2.1 Authentication
- [ ] **JWT with HS256** - rotating secrets, 7-day expiry
- [ ] **Password hashing** - bcrypt/scrypt (not SHA-256)
- [ ] **WebAuthn/Passkeys** - phishing-resistant 2FA
- [ ] **Email-domain allowlist** - only `@iiitdmj.ac.in` for student signup
- [ ] **OTP verification** - 6-digit, 10-min expiry, rate-limited
- [ ] **Brute-force protection** - per-IP sliding window (5/min, 20/5min)

### 2.2 Authorization
- [ ] **Role-based access** - `student` vs `admin` (never self-granted)
- [ ] **Admin-only monitoring endpoints** - JWT with `role: admin`
- [ ] **Read-only monitoring role** - `monitoring_ro` PostgreSQL role
- [ ] **No write tools for scans** - all 8 scans permanently read-only
- [ ] **Tool allowlists per scan** - enforced server-side, not by prompt

### 2.3 Session Management
- [ ] JWT `password_changed_at` invalidates old tokens on reset
- [ ] Passkey `sign_count` validates against cloned authenticators
- [ ] Session timeout configurable (default 7 days)

---
## 3. Data Security

### 3.1 Encryption
- [ ] **TLS 1.2+** enforced everywhere (nginx terminates TLS)
- [ ] **Database encryption at rest** - PostgreSQL `data-checksums`
- [ ] **Secrets in env vars** - never in code, Docker secrets for prod
- [ ] **TELEMETRY_PEPPER** - 32-byte random, required when telemetry enabled
- [ ] **No hardcoded secrets** - `.env.example` only

### 3.2 Database Security
- [ ] **PostgreSQL not published** - internal Docker network only
- [ ] **Read-only monitoring role** - `monitoring_ro` with `default_transaction_read_only = on`
- [ ] **PII columns indexed but not exposed** - `user_hash`, `ip_hash`
- [ ] **Audit tables immutable** - `ScanResult`, `StatusTransition`, `ToolCallAudit` never updated
- [ ] **pg_hba.conf** - restrict to Docker network CIDR

### 3.3 Backup & Recovery
- [ ] **pg_dump + cron** - daily backups with rotation
- [ ] **Tested restore procedure** - documented and tested quarterly
- [ ] **Encrypted backups** - GPG-encrypted before off-site storage
- [ ] **Point-in-time recovery** - WAL archiving enabled

---
## 4. Application Security (OWASP ASVS)

### 4.1 Input Validation
- [ ] **Strict schema validation** - Pydantic models on all endpoints
- [ ] **Event allowlist** - only 19 permitted `event_name` values
- [ ] **Prop size limits** - max 12 props, 120 chars each
- [ ] **Version format regex** - `^[A-Za-z0-9._+\-]{1,32}$`
- [ ] **Country code validation** - ISO 2-letter uppercase only

### 4.2 Output Encoding
- [ ] **No HTML rendering of user content** - feedback text never rendered
- [ ] **JSON-only APIs** - `Content-Type: application/json`
- [ ] **CSP headers** - `default-src 'self'` enforced by nginx

### 4.3 SQL Injection
- [ ] **SQLModel/ORM only** - no raw SQL in application code
- [ ] **Parameterized queries** - SQLAlchemy binds everywhere
- [ ] **Read-only scan role** - `sqlite_ro` authorizer rejects non-SELECT

### 4.4 XSS/CSRF
- [ ] **SameSite=Lax cookies** - JWT in HttpOnly cookie
- [ ] **CSRF tokens** for state-changing forms
- [ ] **Referrer-Policy** - `strict-origin-when-cross-origin`

---
## 5. Monitoring & Telemetry Security

### 5.1 Collector Hardening
- [ ] **Unauthenticated endpoint** - `/collect/*` by necessity
- [ ] **Body size cap** - 200 events/batch, 100KB max
- [ ] **Per-IP rate limiting** - sliding window (30/min events, 10/min crashes)
- [ ] **Event allowlist** - 19 permitted event names only
- [ ] **No raw IP storage** - truncated HMAC-SHA256(pepper, IP)[:32]
- [ ] **No user ID in clear** - HMAC-SHA256(pepper, user_id)

### 5.2 Scan Security
- [ ] **Read-only scans** - no write tools ever granted
- [ ] **Tool allowlists per scan** - enforced server-side by subsection
- [ ] **Reconciliation pass** - every cited metric re-verified (2% tolerance)
- [ ] **Closed action enum** - 12 predefined actions only
- [ ] **Prompt injection defense** - untrusted data wrapped in `<untrusted-data>`
- [ ] **Scan timeout** - 240s hard limit, 1 retry on transport failure
- [ ] **Concurrency limit** - 1 scan at a time (RQ `--concurrency 1`)
- [ ] **Per-tool timeout** - 5s Prometheus, 5s SQL

### 5.3 LLM Safety
- [ ] **Local Ollama only** - no API keys, no egress
- [ ] **CPU-only models** - qwen3:8b (lite), qwen3:30b-a3b (full)
- [ ] **Structured output** - Pydantic + JSON schema validation
- [ ] **Reconciliation pass** - re-query every cited metric (2% tolerance)
- [ ] **Closed action enum** - 12 actions, no free text
- [ ] **Prompt injection guard** - untrusted data in `<untrusted-data>` blocks

---
## 6. Infrastructure Security

### 6.1 Container Security
- [ ] **Non-root containers** - `USER` directive in Dockerfiles
- [ ] **Read-only rootfs** - where possible
- [ ] **No privileged containers** - except cAdvisor (required)
- [ ] **Docker socket read-only** - for cAdvisor/monitoring
- [ ] **Internal network** - no internet egress for tools containers

### 6.2 Network Security
- [ ] **Internal Docker network** - no internet egress for tools
- [ ] **Postgres not published** - internal only
- [ ] **Prometheus not published** - internal only
- [ ] **nginx terminates TLS** - frontend container only
- [ ] **Rate limiting at nginx** - 100 req/s per IP

### 6.3 Supply Chain
- [ ] **Pinned base images** - `postgres:16-alpine`, `ollama/ollama:latest`
- [ ] **Trivy scans** - in CI on every PR
- [ ] **Gitleaks** - secret scanning in CI
- [ ] **Semgrep CE** - SAST in CI
- [ ] **OSV-Scanner** - dependency CVEs in CI (offline DB)
- [ ] **npm audit / pip-audit** - in CI
- [ ] **SBOM generation** - `syft` in CI pipeline

---
## 7. Android Security

### 7.1 Client-Side Signals
- [ ] **Root detection** - RootBeer/Play Integrity (observation only)
- [ ] **Emulator detection** - observation only
- [ ] **Tamper detection** - observation only
- [ ] **Hook/debugger detection** - observation only
- [ ] **Never as auth gate** - signals are telemetry, not auth decisions

### 7.2 Server-Side Validation
- [ ] **Token reuse detection** - same token, different device
- [ ] **Impossible travel** - geo-velocity on auth events
- [ ] **API rate limiting** - per `session_id`
- [ ] **Purchase token replay** - same token, two `user_hash`
- [ ] **APK signature verification** - compare Play install vs self-reported

### 7.3 Build Security
- [ ] **Semgrep CE** - SAST on every PR
- [ ] **Detekt + Android Lint** - in CI
- [ ] **MobSF** - per-release static+dynamic analysis
- [ ] **APKiD** - packer/compiler identification
- [ ] **Gitleaks** - secret scanning

---
## 8. Incident Response

### 8.1 Detection
- [ ] **Prometheus alerts** - 27 rules across 8 subsections
- [ ] **Alertmanager routes** - severity-based routing (critical/security/web/android)
- [ ] **Alerting channels** - Telegram, Webhook, Email (Apprise)
- [ ] **No alert fatigue** - only actionable alerts, for 3am on-call

### 8.2 Response
- [ ] **Runbook for each critical alert** - documented in `ops/runbooks/`
- [ ] **ZAP active scan** - only against staging clone with seeded DB
- [ ] **Rollback procedure** - `ROLLBACK_RELEASE` action in scan enum
- [ ] **Credential rotation** - `ROTATE_CREDENTIALS` action
- [ ] **Rate limit adjustment** - `ADD_RATE_LIMIT` action

### 8.3 Forensics
- [ ] **Tool call audit log** - every LLM tool call recorded
- [ ] **Scan result history** - immutable, with confidence metadata
- [ ] **Incident log** - derived from `StatusTransition` table
- [ ] **Post-mortem template** - blameless, within 48h

---
## 9. Compliance & Legal

### 9.1 DPDP Act (India)
- [ ] **Consent manager** - granular, revocable
- [ ] **Data Protection Officer** - designated contact
- [ ] **Breach notification** - within 72h to DPDP board
- [ ] **Data processing agreements** - with all subprocessors
- [ ] **Children's data** - handle under-18 per DPDP Sec. 9

### 9.2 Open Source Licensing
- [ ] **All components OSI-approved** - MIT, Apache-2.0, BSD-3, GPL-2/3
- [ ] **No Elastic/SSPL/BSL** - excluded per zero-cost rules
- [ ] **License audit** - `license-checker` in CI
- [ ] **Attribution** - `THIRD_PARTY_LICENSES` file in repo

### 9.3 Export Controls
- [ ] **No crypto export restrictions** - standard TLS only
- [ ] **No dual-use tech** - pure application software

---
## 10. Operational Security

### 10.1 Access Control
- [ ] **SSH keys only** - no password auth on servers
- [ ] **Bastion host** - single entry point
- [ ] **Audit logging** - all admin actions logged
- [ ] **Key rotation** - SSH keys rotated annually

### 10.2 Monitoring the Monitor
- [ ] **Prometheus self-monitoring** - `up{job="prometheus"}`
- [ ] **Telemetry collector health** - `absent(campuspilot_collector_events_total)`
- [ ] **Rollup job monitoring** - lag alert > 2h
- [ ] **Scan worker health** - queue depth, latency metrics

### 10.3 Disaster Recovery
- [ ] **RTO < 4h** - automated failover to backup
- [ ] **RPO < 1h** - WAL streaming replication
- [ ] **Chaos engineering** - quarterly failure injection
- [ ] **Runbook testing** - monthly drill

---
## ✅ Sign-off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Security Lead | | | |
| Data Protection Officer | | | |
| Engineering Lead | | | |
| Legal/Compliance | | | |

---
*Document version: 1.0 | Last updated: 2026-10-08 | Next review: 2027-01-08*
*This checklist is a living document - update with each major release*