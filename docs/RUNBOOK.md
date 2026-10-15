# CampusPilot Admin Platform - Operations Runbook

## Overview
This runbook covers day-to-day operations, incident response, and maintenance procedures for the CampusPilot Admin Platform.

---

## Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Frontend      │────▶│   Backend API   │────▶│  PostgreSQL     │
│  (React/Vite)   │     │  (FastAPI)      │     │  (Primary)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                              │
                              ▼
                        ┌─────────────────┐
                        │   Redis         │
                        │  (Cache/Queue)  │
                        └─────────────────┘
```

---

## Common Operations

### 1. Adding a New Feature Flag
```bash
# 1. Create flag via API
curl -X POST http://localhost:8001/admin/flags \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "feature.new-feature",
    "name": "New Feature",
    "description": "Enable new feature",
    "enabled": true,
    "rollout_percentage": 10,
    "target_roles": ["student"],
    "target_platforms": ["web", "android"]
  }'

# 2. Verify in UI: Admin Panel → Control → Feature Flags
# 3. Test rollout: Toggle enabled/disabled, adjust percentage
```

**Rollback**: Set `enabled: false` or `rollout_percentage: 0`

---

### 2. Enabling Maintenance Mode
```bash
# Global maintenance
curl -X POST http://localhost:8001/admin/maintenance \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Scheduled Maintenance",
    "global_maintenance": true,
    "message": "System maintenance in progress. Please try again later.",
    "scheduled_start": "2024-01-15T02:00:00Z",
    "scheduled_end": "2024-01-15T04:00:00Z",
    "bypass_roles": ["admin"]
  }'

# Feature-specific maintenance
curl -X POST http://localhost:8001/admin/maintenance \
  -H "Authorization: Bearer <admin_token>" \
  -d '{
    "name": "Timetable Migration",
    "global_maintenance": false,
    "target_features": ["timetable"],
    "message": "Timetable service temporarily unavailable"
  }'
```

**Verify**: Check `/health/ready` returns 503 with maintenance message

---

### 3. Updating Remote Config
```bash
# Create config
curl -X POST http://localhost:8001/admin/remote-config \
  -H "Authorization: Bearer <admin_token>" \
  -d '{
    "key": "app.max_file_size_mb",
    "value": {"max": 50, "allowed_types": ["pdf", "docx"]},
    "value_type": "json",
    "schema_json": {"type": "object", "properties": {"max": {"type": "integer"}, "allowed_types": {"type": "array"}}},
    "description": "Max file upload size and allowed types"
  }'

# Update value
curl -X PATCH http://localhost:8001/admin/remote-config/app.max_file_size_mb \
  -H "Authorization: Bearer <admin_token>" \
  -d '{"value": {"max": 100, "allowed_types": ["pdf", "docx", "pptx"]}}'

# Rollback
curl -X POST http://localhost:8001/admin/remote-config/app.max_file_size_mb/rollback \
  -H "Authorization: Bearer <admin_token>" \
  -d '{"version": 1}'
```

---

### 4. Sending Broadcasts
```bash
# In-app notification to all students
curl -X POST http://localhost:8001/admin/broadcasts \
  -H "Authorization: Bearer <admin_token>" \
  -d '{
    "title": "Campus Event",
    "body": "Tech Fest starts tomorrow at 10 AM!",
    "channel": "in_app",
    "target_roles": ["student"]
  }'

# Push notification to specific branch
curl -X POST http://localhost:8001/admin/broadcasts \
  -H "Authorization: Bearer <admin_token>" \
  -d '{
    "title": "Exam Schedule Update",
    "body": "CS101 exam moved to 3 PM",
    "channel": "push",
    "target_branches": ["CSE"],
    "target_semesters": [5]
  }'
```

---

### 5. Force/Soft Update Rules
```bash
# Force update for iOS
curl -X POST http://localhost:8001/admin/force-update \
  -H "Authorization: Bearer <admin_token>" \
  -d '{
    "platform": "ios",
    "min_version": "2.1.0",
    "recommended_version": "2.2.0",
    "store_url": "https://apps.apple.com/app/id12345",
    "message": "Critical security update required"
  }'

# Soft update for Android
curl -X POST http://localhost:8001/admin/force-update \
  -H "Authorization: Bearer <admin_token>" \
  -d '{
    "platform": "android",
    "min_version": "1.0.0",
    "recommended_version": "2.1.0",
    "store_url": "https://play.google.com/store/apps/details?id=com.campuspilot",
    "message": "New features available"
  }'
```

**Client check**: `GET /admin/force-update/check?platform=ios&version=2.0.0`

---

### 6. User Management Actions
```bash
# Suspend user (30 days)
curl -X POST http://localhost:8001/admin/users/123/suspend \
  -H "Authorization: Bearer <admin_token>" \
  -d '{"reason": "Policy violation", "duration_days": 30}'

# Ban user permanently
curl -X POST http://localhost:8001/admin/users/123/ban \
  -H "Authorization: Bearer <admin_token>" \
  -d '{"reason": "Repeated policy violations"}'

# Force logout (revokes all sessions)
curl -X POST http://localhost:8001/admin/users/123/force-logout \
  -H "Authorization: Bearer <admin_token>" \
  -d '{"reason": "Security audit"}'

# Bulk suspend
curl -X POST http://localhost:8001/admin/users/bulk \
  -H "Authorization: Bearer <admin_token>" \
  -d '{
    "user_ids": [123, 124, 125],
    "action": "suspend",
    "reason": "Batch suspension",
    "duration_days": 7
  }'
```

---

### 7. Content Moderation
```bash
# List pending moderation
curl -X GET http://localhost:8001/admin/moderation \
  -H "Authorization: Bearer <admin_token>"

# Review and approve
curl -X PATCH http://localhost:8001/admin/moderation/123/review \
  -H "Authorization: Bearer <admin_token>" \
  -d '{"action": "approve", "reason": "Content appropriate"}'

# Remove content
curl -X PATCH http://localhost:8001/admin/moderation/123/review \
  -H "Authorization: Bearer <admin_token>" \
  -d '{"action": "remove", "reason": "Violates community guidelines"}'
```

---

### 7. Analytics & Anomaly Detection
```bash
# Run daily aggregation
curl -X POST http://localhost:8001/admin/analytics/aggregate/daily \
  -H "Authorization: Bearer <admin_token>"

# Detect anomalies
curl -X POST http://localhost:8001/admin/analytics/anomalies/detect \
  -H "Authorization: Bearer <admin_token>"

# View overview
curl -X GET "http://localhost:8001/admin/analytics/overview?days=7" \
  -H "Authorization: Bearer <admin_token>"
```

---

## Incident Response

### Alert: High Error Rate
```bash
# 1. Check Errors tab in Admin Panel
# 2. Check error fingerprint grouping
# 3. Check recent deployments
# 4. If recent deploy: rollback
# 5. If not: check logs, scale resources

# Quick rollback
kubectl rollout undo deployment/backend -n campuspilot
```

### Alert: High Failed Login Rate
```bash
# 1. Check Security Feed for brute force alerts
# 2. Check rate limiter status
# 3. If attack: enable stricter rate limiting
# 4. Block suspicious IPs at firewall

# Emergency rate limit increase
curl -X PATCH http://localhost:8001/admin/settings/rate_limiting_enabled \
  -H "Authorization: Bearer <admin_token>" \
  -d '{"value": true}'
```

### Alert: Database Performance
```bash
# 1. Check /health/ready for DB status
# 2. Check slow query logs
# 3. Check connection pool usage
# 4. If needed: scale read replicas or increase pool size

# Emergency: kill long-running queries
psql -U campuspilot -d campuspilot -c "
  SELECT pg_terminate_backend(pid) 
  FROM pg_stat_activity 
  WHERE state = 'active' AND now() - query_start > interval '5 minutes';
"
```

### Alert: High Memory/CPU
```bash
# 1. Check /health/live and /health/ready
# 2. Check container resource limits
# 3. If OOM: restart pods with higher limits
# 4. If CPU: check for runaway processes

# Quick restart
kubectl rollout restart deployment/backend -n campuspilot
```

---

## Maintenance Procedures

### Daily
- [ ] Check `/health/ready` - all green
- [ ] Review Security Feed for anomalies
- [ ] Check error rate in Errors tab
- [ ] Verify backup completed

### Weekly
- [ ] Run `alembic upgrade heads` on staging
- [ ] Review feature flag usage (cleanup unused)
- [ ] Review broadcast delivery stats
- [ ] Check disk space (`df -h`)
- [ ] Review security feed for unresolved incidents

### Monthly
- [ ] Rotate secrets (JWT secret, DB password, SMTP)
- [ ] Run `alembic upgrade heads` on production (maintenance window)
- [ ] Review feature flag usage report
- [ ] Archive old audit logs (>90 days)
- [ ] Update dependencies (security patches)
- [ ] Run full backup restore test

### Quarterly
- [ ] Disaster recovery drill
- [ ] Review and update runbook
- [ ] Penetration test
- [ ] Capacity planning review

---

## Adding a New Feature

1. **Backend scaffold**:
   ```bash
   python backend/app/scripts/scaffold_feature.py "my-feature"
   ```

2. **Add model to models.py** (if new table)

3. **Create Alembic migration**:
   ```bash
   alembic revision --autogenerate -m "add my_feature table"
   alembic upgrade heads
   ```

3. **Implement routes, service, models**

4. **Add to main.py router includes**

5. **Frontend**:
   ```bash
   node scaffold-feature.js my-feature
   ```

3. **Add to AdminPanel.tsx tabs**

4. **Extend adminApi in api.ts**

4. **Write tests** (auth matrix + behavior)

5. **Run tests**: `pytest tests/test_my_feature.py -v`

6. **Deploy**: CI/CD handles rest

---

## Rollback Procedures

### Feature Flag Rollback
```bash
# Immediate: disable flag
curl -X PATCH http://localhost:8001/admin/flags/feature.xxx \
  -H "Authorization: Bearer <admin_token>" \
  -d '{"enabled": false}'
```

### Config Rollback
```bash
curl -X POST http://localhost:8001/admin/remote-config/key/rollback \
  -H "Authorization: Bearer <admin_token>" \
  -d '{"version": 1}'
```

### Database Migration Rollback
```bash
# Single step
alembic downgrade -1

# To specific revision
alembic downgrade <revision_id>
```

### Full Deployment Rollback
```bash
kubectl rollout undo deployment/backend -n campuspilot
kubectl rollout undo deployment/frontend -n campuspilot
```

---

## Key Contacts & Escalation

| Role | Contact | Escalation Time |
|------|---------|-----------------|
| On-call Engineer | Slack #oncall | 15 min |
| Team Lead | Slack #team-leads | 30 min |
| Engineering Manager | Slack #eng-mgmt | 1 hour |
| CTO | Direct | 2 hours |

---

## Useful Commands Reference

```bash
# Health checks
curl http://localhost:8001/health/live
curl http://localhost:8001/health/ready

# Metrics
curl http://localhost:8001/metrics

# Alembic
alembic current
alembic history
alembic upgrade heads
alembic downgrade -1

# Database
psql -U campuspilot -d campuspilot -c "SELECT * FROM pg_stat_activity;"
psql -U campuspilot -d campuspilot -c "SELECT * FROM pg_locks;"

# Logs
kubectl logs -f deployment/backend -n campuspilot --tail=100
kubectl logs -f deployment/frontend -n campuspilot --tail=100

# Database backup
pg_dump -U campuspilot campuspilot > backup_$(date +%Y%m%d).sql

# Restore
psql -U campuspilot campuspilot < backup_20240115.sql
```

---

## Appendix: Feature Flag Reference

| Flag Key | Purpose | Default | Targeting |
|----------|---------|---------|-----------|
| `feature.timetable_v2` | New timetable parser | false | student, 10% |
| `feature.exam_v2` | New exam UI | false | student, 20% |
| `feature.analytics_v2` | New analytics pipeline | false | admin, 100% |
| `feature.push_notifications` | Push notifications | false | student, 50% |
| `feature.ai_assist` | AI study assistant | false | student, 5% |
| `feature.dark_mode` | Dark theme | true | all, 100% |
| `maintenance.timetable` | Timetable maintenance | false | - |
| `maintenance.exam` | Exam maintenance | false | - |

---

*Last Updated: 2024-10-15 | Version 1.0*
*Next Review: 2024-11-15*