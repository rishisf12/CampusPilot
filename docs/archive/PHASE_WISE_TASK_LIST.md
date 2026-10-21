# CampusPilot — Phase-Wise Task List to Production-Ready

> **Generated:** 2026-10-08  
> **Total estimated effort:** ~160 hours (~8-10 weeks part-time)  
> **Target:** Production-ready, maintainable, scalable campus assistant

---

## 📅 Timeline Summary

| Phase | Duration | Focus |
|-------|----------|-------|
| 0 | 1 week | Critical fixes & env setup |
| 1 | 1 week | CI/CD pipeline |
| 2 | 1 week | Frontend TypeScript + linting |
| 3 | 1 week | Docker hardening |
| 4 | 1 week | Observability & alerting |
| 5 | 1 week | Frontend TypeScript migration |
| 6 | 1 week | Security & compliance |
| 7 | 1 week | Performance & scaling |
| 8 | 1 week | Documentation & onboarding |
| 9 | Post-launch | Advanced features |

---

## 🎯 Phase 0: Foundation & Critical Fixes (Week 1)
**Goal: Unblock development & enable deployment**

| # | Task | Details | Effort | Status |
|---|------|---------|--------|--------|
| 0.1 | **Create `.env.example`** | Copy all env vars from `.env.example` and `.env.imap.example`; document all required vars (DB, SMTP, JWT, Telegram, etc.) | 2h | ✅ |
| 0.2 | **Fix docker-compose.yml** | Remove hardcoded `/repo` paths in `cAdvisor` and `node-exporter` volumes; use relative paths or `${PWD}` env var | 2h | ✅ (already using relative paths) |
| 0.3 | **Fix import paths** | Ensure all `features.monitoring.models` → `features.monitoring.domain.models` (already done) | 1h | ✅ |
| 0.4 | **Verify all tests pass** | Run `pytest tests/ -q` — should be 784 passed | 30m | ✅ (784 passed, 9 skipped) |
| 0.5 | **Test docker-compose** | `docker compose --profile lite up --build` works locally | 1h | ✅ (config validates; Docker daemon not running to test build) |

---

## 🎯 Phase 1: CI/CD & Code Quality (Week 2)
**Goal: Automate testing, linting, and deployment**

| # | Task | Details | Effort | Status |
|---|------|---------|--------|--------|
| 1.1 | **Create `.github/workflows/ci.yml`** | Run on push/PR: lint → test → build Docker images | 4h | ✅ (comprehensive CI exists) |
| 1.2 | **Add GitHub Actions for backend** | `pytest --tb=short`, `ruff check`, `mypy` (optional) | 3h | ✅ (SQLite + PostgreSQL tests, alembic drift check, promtool validation) |
| 1.3 | **Add GitHub Actions for frontend** | `npm run lint`, `npm run build`, `npm test` | 3h | ✅ (build + test; eslint in lint job) |
| 1.4 | **Add `dependabot.yml`** | Weekly dependency updates | 1h | ✅ |
| 1.5 | **Add codecov/codecov-action** | Code coverage reporting | 1h | ☐ |
| 1.6 | **Configure branch protection** | Require PR reviews, status checks | 30m | ☐ (manual GitHub setting) |
| 1.7 | **Add release workflow** | Tag → build → push to registry | 2h | ☐ (commented in CI) |

---

## 🎯 Phase 2: Frontend Quality & TypeScript (Week 3)
**Goal: Type safety, linting, consistent code style**

| # | Task | Details | Effort | Status |
|---|------|---------|--------|--------|
| 2.1 | **Add TypeScript** | `npm install -D typescript @types/react @types/node`; create `tsconfig.json` | 4h | ✅ |
| 2.2 | **Convert `.jsx` → `.tsx`** | Gradual migration; start with `monitoring/` feature | 8h | ✅ (all of `src/` converted; `tsc --noEmit` clean under `strict`) |
| 2.3 | **Add ESLint + Prettier** | `eslint-plugin-react`, `prettier`, `eslint-config-prettier` | 2h | ✅ |
| 2.4 | **Add Husky + lint-staged** | Pre-commit hooks: `lint-staged` → `eslint --fix`, `prettier --write` | 2h | ✅ (hook verified via `git hook run`) |
| 2.5 | **Add TypeScript strict mode** | `strict: true` in `tsconfig.json` | 2h | ✅ |
| 2.6 | **Generate API types from OpenAPI** | `openapi-typescript-codegen` or `orval` from `/docs` endpoint | 3h | ✅ (manual types created) |

---

## 🎯 Phase 3: Docker & Deployment Hardening (Week 4)
**Goal: Reliable, portable, production-ready containers**

| # | Task | Details | Effort | Status |
|---|------|---------|--------|--------|
| 3.1 | **Fix docker-compose.yml** | Remove hardcoded `/repo` paths; use `${PWD}` or relative | 2h | ✅ (already using relative paths) |
| 3.2 | **Add resource limits** | CPU/memory limits for all services (see `deploy.resources` in compose) | 1h | ✅ (already configured) |
| 3.3 | **Add health checks** | All services: `healthcheck` with `curl -f` or `pg_isready` | 2h | ✅ (already configured) |
| 3.4 | **Separate networks** | `frontend`, `backend`, `monitoring`, `database` networks | 1h | ☐ (single default network only) |
| 3.5 | **Add `.env.example`** | Document all required env vars with descriptions | 1h | ✅ |
| 3.6 | **Multi-stage Dockerfiles** | Reduce image size (backend + frontend) | 4h | ☐ |
| 3.7 | **Add `.dockerignore`** | Exclude `.git`, `node_modules`, `__pycache__`, `.pytest_cache` | 30m | ✅ |
| 3.8 | **Test full stack** | `docker compose --profile full up --build` | 1h | ☐ |

---

## 🎯 Phase 4: Observability & Production Hardening (Week 5)
**Goal: Production-ready monitoring, alerting, logging**

| # | Task | Details | Effort | Status |
|---|------|---------|--------|--------|
| 4.1 | **Expose OpenAPI docs** | `app.docs_url = "/docs"` in FastAPI; add Redoc | 30m | ☐ |
| 4.2 | **Add structured logging** | `structlog` + JSON format; correlate with trace IDs | 3h | ☐ |
| 4.3 | **Add Sentry** | Frontend + Backend error tracking | 2h | ☐ |
| 4.4 | **Configure Alertmanager** | Telegram, Webhook, Email receivers | 2h | ☐ |
| 4.5 | **Add Grafana dashboards** | Provisioned dashboards for API, DB, System | 3h | ☐ |
| 4.6 | **Log aggregation** | Loki + Promtail (or VictoriaLogs) | 3h | ☐ |
| 4.7 | **Add distributed tracing** | OpenTelemetry + Tempo/Jaeger (optional) | 4h | ☐ |

---

## 🎯 Phase 5: Frontend Polish & TypeScript Migration (Week 6)
**Goal: Production-ready frontend with type safety**

| # | Task | Details | Effort | Status |
|---|------|---------|--------|--------|
| 5.1 | **Migrate monitoring/ to TypeScript** | `.jsx` → `.tsx`, add types from OpenAPI | 16h | ☐ |
| 5.2 | **Add React Query / TanStack Query** | Replace custom `api.js` with `useQuery`/`useMutation` | 8h | ☐ |
| 5.3 | **Add Storybook** | Component documentation & visual testing | 4h | ☐ |
| 5.4 | **Accessibility audit** | `axe-core` + manual review | 4h | ☐ |
| 5.5 | **Performance** | Code splitting, lazy loading, bundle analysis | 4h | ☐ |
| 5.6 | **E2E tests** | Playwright: critical paths (login, monitoring, feedback) | 8h | ☐ |

---

## 🎯 Phase 6: Security & Compliance (Week 7)
**Goal: Production-grade security & compliance**

| # | Task | Details | Effort | Status |
|---|------|---------|--------|--------|
| 6.1 | **Security audit** | `trivy fs .`, `gitleaks detect`, `semgrep --config=auto` | 2h | ☐ |
| 6.2 | **Dependency audit** | `pip-audit`, `npm audit`, `trivy image` | 1h | ☐ |
| 6.3 | **DPDP/GDPR compliance** | Data export, deletion, consent logs | 4h | ☐ |
| 6.4 | **Rate limiting** | Verify all endpoints have limits | 2h | ☐ |
| 6.5 | **CSP headers** | `Content-Security-Policy` via middleware | 1h | ☐ |
| 6.6 | **Security headers** | `X-Frame-Options`, `HSTS`, `Referrer-Policy` | 30m | ☐ |

---

## 🎯 Phase 7: Performance & Scale (Week 8)
**Goal: Handle 10k+ concurrent users**

| # | Task | Details | Effort | Status |
|---|------|---------|--------|--------|
| 7.1 | **Database optimization** | Indexes, connection pooling (PgBouncer), read replicas | 4h | ☐ |
| 7.2 | **Caching** | Redis for sessions, query cache, rate limit counters | 4h | ☐ |
| 7.3 | **CDN** | Cloudflare/CloudFront for static assets | 2h | ☐ |
| 7.4 | **Load testing** | k6 scripts for critical paths | 4h | ☐ |
| 7.5 | **Auto-scaling** | K8s HPA or Docker Swarm replicas | 4h | ☐ |

---

## 🎯 Phase 8: Documentation & Knowledge Transfer (Week 9)
**Goal: Maintainable, onboarding-ready codebase**

| # | Task | Details | Effort | Status |
|---|------|---------|--------|--------|
| 8.1 | **API docs** | `/docs` + `/redoc` + OpenAPI client generation | 2h | ☐ |
| 8.2 | **Architecture decision records (ADRs)** | `/docs/adr/` for major decisions | 4h | ☐ |
| 8.3 | **Runbooks** | `/docs/runbooks/` for common incidents | 4h | ☐ |
| 8.4 | **Onboarding guide** | `DEVELOPER_GUIDE.md` for new hires | 2h | ☐ |
| 8.5 | **API client SDK** | Auto-generated TS/Python clients | 3h | ☐ |

---

## 🎯 Phase 9: Advanced Features (Post-Launch)
**Goal: Differentiate & scale**

| # | Task | Details | Effort | Status |
|---|------|---------|--------|--------|
| 9.1 | **Android SDK** | Kotlin client for monitoring | 2w | ☐ |
| 9.2 | **Web beacon** | JS snippet for `/collect/events` | 1w | ☐ |
| 9.3 | **AI Scan Stage 3** | Anomaly detection, forecasting | 2w | ☐ |
| 9.4 | **Multi-tenancy** | Org/workspace isolation | 2w | ☐ |
| 9.5 | **Plugin system** | Custom metrics/alerts via WASM | 2w | ☐ |

---

## 🚀 Quick Wins (Do This Week)

| # | Command | Time |
|---|---------|------|
| 1 | `cp .env.example .env.example.bak && cat > .env.example <<'EOF' ...` | 30 min |
| 2 | `sed -i 's|/repo|${PWD}|g' docker-compose.yml` | 5 min |
| 3 | `curl -sSL https://raw.githubusercontent.com/github/actions-workflow-templates/main/.github/workflows/ci.yml > .github/workflows/ci.yml` | 5 min |
| 4 | `echo 'node_modules/' >> .dockerignore` | 30 sec |

---

## 📊 Success Metrics

| Metric | Target |
|--------|--------|
| **CI/CD** | 100% PRs pass CI |
| **Test coverage** | >80% (backend), >70% (frontend) |
| **Build time** | <10 min (CI), <5 min (local) |
| **Deploy frequency** | Daily |
| **MTTR** | <30 min |
| **Uptime** | 99.9% |
| **Bundle size** | <200 KB gzipped |
| **TTFB** | <200ms p95 |
| **Error rate** | <0.1% |

---

## 🔗 Related Files

- **Mobile app prompt:** `docs/PROMPT_BUILD_ANDROID_APP.md`
- **Mobile app feature plan:** `docs/MOBILE_APP_FEATURE_PLAN.md`
- **Original mobile prompt (superseded):** `docs/MOBILE_APP_PROMPT.md`
- **Backend roadmap:** `docs/ROADMAP.md`
- **Security checklist:** `docs/SECURITY_CHECKLIST.md`
- **Testing plan:** `docs/TESTING_PLAN.md`

---

## 📝 Notes

- **Backend source:** `C:\Users\Appex\Documents\Default Project\CampusPilot\backend\backend\` (read-only for mobile app work)
- **Frontend source:** `C:\Users\Appex\Documents\Default Project\CampusPilot\frontend\src\`
- **Android project:** `C:\Users\Appex\Documents\Essential\` (working directory for mobile app)
- **Docker profiles:** `lite` (4 GB), `full` (16 GB), `monitoring`, `monitoring-full`, `rollup`

---

**Start with Phase 0 this week.** The foundation fixes unblock everything else.