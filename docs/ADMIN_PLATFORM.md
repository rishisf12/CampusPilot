# CampusPilot Admin Platform - Architecture & API Reference

## Overview

The CampusPilot Admin Platform is a comprehensive control, monitoring, and analytics suite built on top of the CampusPilot application. It provides administrators with full visibility and control over users, content, system health, and product analytics.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Admin Platform Architecture                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────┐  │
│  │   Frontend   │───▶│  Backend API │───▶│  PostgreSQL  │    │  Redis   │  │
│  │  (React)     │    │  (FastAPI)   │    │  (Primary)   │    │ (Cache)  │  │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────────┘  │
│         │                    │                   │                   │      │
│         ▼                    ▼                   ▼                   ▼      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Admin Panel (Lazy-loaded Modules)                │   │
│  ├──────────────┬──────────────┬──────────────┬──────────────┬────────┤   │
│  │   Control    │  Monitoring  │    Errors    │   Analytics  │ User360│   │
│  ├──────────────┼──────────────┼──────────────┼──────────────┼────────┤   │
│  │  Security    │    Audit     │  Settings    │  User Mgmt   │ Teams  │   │
│  └──────────────┴──────────────┴──────────────┴──────────────┴────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Modules

### 1. Control (`/admin/control`)
**Feature Flags, Maintenance Mode, Remote Config**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /admin/flags` | GET | List feature flags with filtering |
| `POST /admin/flags` | POST | Create feature flag |
| `PATCH /admin/flags/{key}` | PATCH | Update feature flag |
| `DELETE /admin/flags/{key}` | DELETE | Delete feature flag |
| `GET /admin/maintenance` | GET | List maintenance windows |
| `POST /admin/maintenance` | POST | Create maintenance window |
| `PATCH /admin/maintenance/{id}` | PATCH | Update maintenance window |
| `GET /admin/remote-config` | GET | List remote configs |
| `POST /admin/remote-config` | POST | Create remote config |
| `PATCH /admin/remote-config/{key}` | PATCH | Update remote config |
| `POST /admin/remote-config/{key}/rollback` | POST | Rollback config to version |

**Feature Flag Targeting:**
- Roles: `student`, `admin`
- Platforms: `web`, `ios`, `android`
- App versions: semantic version patterns
- User IDs: explicit user targeting
- Rollout percentage: 0-100%

**Maintenance Mode:**
- Global or per-feature
- Scheduled start/end
- Allow-list bypass
- Role bypass (admins always bypass)

---

### 2. Monitoring (`/admin/monitoring`)
**Live Health, Error Tracking, Alerts**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /monitoring/live` | GET | Real-time system health |
| `GET /monitoring/errors` | GET | Error feed with grouping |
| `PATCH /monitoring/errors/{id}` | PATCH | Update error status |
| `GET /monitoring/health` | GET | Component health checks |
| `GET /monitoring/alerts` | GET | List alert rules |
| `POST /admin/alerts/rules` | POST | Create alert rule |

**Health Checks:**
- Database connectivity
- Redis connectivity
- Disk space
- Memory usage
- CPU usage
- Background job status

**Error Tracking:**
- Automatic fingerprint grouping
- Status: `new`, `investigating`, `resolved`, `ignored`
- Assignee tracking
- First/last seen timestamps
- Affected users count

**Alert Rules:**
- Metrics: error_rate, p95_latency, crash_free_rate, failed_logins
- Conditions: gt, lt, gte, lte, eq
- Channels: email, Slack, Discord webhook
- Cooldown, severity, acknowledgment

---

### 3. Analytics (`/admin/analytics`)
**Product & User Analytics**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /admin/analytics/overview` | GET | DAU/WAU/MAU, retention, signups |
| `GET /admin/analytics/feature-usage` | GET | Feature adoption metrics |
| `GET /admin/analytics/retention` | GET | D1/D7/D30 retention cohorts |
| `GET /admin/analytics/platforms` | GET | Platform/version distribution |
| `POST /admin/analytics/aggregate/daily` | POST | Run daily aggregation |
| `GET /admin/analytics/events` | GET | Query raw events |
| `POST /admin/analytics/track` | POST | Track custom event |
| `POST /admin/analytics/anomalies/detect` | POST | Run anomaly detection |

**Anomaly Detection:**
- 7-day baseline ±3σ
- Metrics: DAU, signups, feature usage, retention
- Severity: warning (≥3σ), critical (≥5σ)
- Plain-language explanations

**Segments:**
- Saved user segments with DSL criteria
- Usable in broadcasts and feature flags
- Example: `"inactive 14d, Android, v<3.2"`

**Funnels:**
- Multi-step conversion tracking
- Windowed analysis
- Drop-off visualization

---

### 4. User 360 (`/admin/users/{id}/360`)
**Complete User Profile**

**Tabs:**
- Profile: demographics, branch, semester
- Devices: registered devices, push tokens
- Sessions: active sessions, history
- Errors: recent errors affecting user
- Features: feature usage per user
- Teams: team memberships
- Moderation: moderation history
- Audit: user-specific audit trail

**Actions:**
- Suspend/Ban/Force logout
- Revoke tokens
- Reset verification
- Impersonate (read-only view)

---

### 5. User Management (`/admin/users`)
**User Administration**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /admin/users` | GET | List users with search/filter |
| `PATCH /admin/users/{id}/role` | PATCH | Change user role |
| `GET /admin/stats` | GET | User statistics |

**Actions:**
- Promote to admin / Demote to student
- Self-demotion prevention
- Search by email, username, name, roll number
- Role filter: admin/student
- Pagination

---

### 6. Broadcasts (`/admin/broadcasts`)
**In-App & Push Notifications**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /admin/broadcasts` | GET | List broadcasts |
| `POST /admin/broadcasts` | POST | Create broadcast |
| `POST /admin/broadcasts/{id}/send` | POST | Send broadcast |
| `GET /admin/broadcasts/{id}/deliveries` | GET | Delivery statistics |

**Targeting:**
- Roles: student, admin
- Branches: CSE, ECE, ME, etc.
- Semesters: 1-8
- Segments: saved user segments
- Explicit user IDs

**Channels:**
- In-app (all platforms)
- Push (FCM/APNs ready)
- Email (future)

---

### 6. Force/Soft Updates (`/admin/force-update`)
**App Version Management**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /admin/force-update` | GET | List update rules |
| `POST /admin/force-update` | POST | Create update rule |
| `PATCH /admin/force-update/{platform}` | PATCH | Update rule |
| `GET /admin/force-update/check` | GET | Client update check |

**Rule Types:**
- Force update: blocks app until updated
- Soft update: shows banner, user can dismiss
- Per-platform: iOS, Android, Web
- Store links: App Store, Play Store

---

### 7. Security (`/admin/security`)
**Security Monitoring**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /admin/security/events` | GET | Recent security events |
| `GET /admin/security/feed` | GET | Aggregated security feed |
| `POST /admin/security/anomalies/detect` | POST | Run anomaly detection |

**Event Types:**
- `failed_login`: Failed authentication
- `brute_force`: Brute force detection
- `new_admin`: New admin account created
- `role_change`: User role changed
- `unusual_ip`: Login from new IP
- `rate_limit`: Rate limit exceeded

**Severity Levels:**
- `low`: Informational
- `medium`: Warning
- `high`: Action required
- `critical`: Immediate action

---

### 8. Audit Log (`/admin/audit`)
**Immutable Audit Trail**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /admin/audit` | GET | Filtered audit log |
| `GET /admin/audit/export` | GET | Export JSON/CSV |

**Logged Actions:**
- User role changes
- Feature flag toggles
- Config changes
- User suspensions/bans
- Broadcast sends
- Config rollbacks
- Maintenance toggles

**Export Formats:**
- JSON: Full fidelity
- CSV: Spreadsheet compatible

---

### 9. Settings (`/admin/settings`)
**System Configuration**

| Setting | Type | Description |
|---------|------|-------------|
| `rate_limiting_enabled` | bool | Enable API rate limiting |
| `brute_force_protection` | bool | Lock accounts after failed attempts |
| `password_min_length` | int | Minimum password length |
| `default_rollout_percentage` | int | Default flag rollout % |
| `default_maintenance_message` | string | Default maintenance message |
| `alert_email` | string | Email for system alerts |
| `slack_webhook_url` | string | Slack webhook for alerts |
| `ios_app_store_url` | string | iOS App Store URL |
| `android_play_store_url` | string | Android Play Store URL |

---

### 10. Teams Moderation (`/admin/teams`)
**Team Management**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /admin/teams` | GET | List all teams |
| `DELETE /admin/teams/{id}` | DELETE | Delete team (moderation) |

---

### 11. Force/Soft Update Client Check
**Client-Facing Endpoint**

```
GET /admin/force-update/check?platform=ios&version=2.1.0
```

**Response:**
```json
{
  "required": true,
  "type": "force",
  "min_version": "2.1.0",
  "recommended_version": "2.2.0",
  "store_url": "https://apps.apple.com/app/id12345",
  "message": "Critical security update required"
}
```

**Types:**
- `force`: Block app usage until updated
- `soft`: Show banner, dismissible
- `none`: No update needed

---

## Authentication & Authorization

### Admin Guard
All admin endpoints require `get_current_admin` dependency:
- **401**: Anonymous/unauthenticated
- **403**: Authenticated but non-admin
- **200**: Admin user

### Permissions Model
- **SUPER_ADMIN**: Full access (current `ADMIN` role)
- **MODERATOR**: Content moderation, user actions
- **ANALYST**: Read-only analytics access
- **STUDENT**: No admin access

---

## Error Handling

### Standard Error Response
```json
{
  "detail": "Error message",
  "status_code": 400
}
```

### Common Status Codes
| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 204 | No Content |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 422 | Validation Error |
| 429 | Rate Limited |
| 500 | Server Error |
| 503 | Maintenance Mode |

---

## Rate Limiting

| Endpoint | Limit |
|----------|-------|
| Auth endpoints | 10 req/min |
| Admin endpoints | 100 req/min |
| Broadcast send | 5 req/min |
| Analytics queries | 30 req/min |
| Error ingestion | 100 req/min |

---

## Monitoring Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health/live` | Liveness probe |
| `GET /health/ready` | Readiness probe |
| `GET /metrics` | Prometheus metrics |

---

## Webhook Integration

### Alert Webhooks
```json
{
  "alert_id": 123,
  "rule_name": "High Error Rate",
  "severity": "critical",
  "metric": "error_rate",
  "value": 0.15,
  "threshold": 0.05,
  "started_at": "2024-01-15T10:30:00Z",
  "status": "firing"
}
```

### Broadcast Delivery Webhook
```json
{
  "broadcast_id": 123,
  "user_id": 456,
  "channel": "push",
  "status": "delivered",
  "sent_at": "2024-01-15T10:30:00Z"
}
```

---

## Database Schema Reference

### Core Tables
| Table | Schema | Purpose |
|-------|--------|---------|
| `core.user` | core | User accounts |
| `core.user_profile` | core | Extended profile |
| `core.audit_log` | core | Immutable audit trail |
| `core.feature_flag` | core | Feature flags |
| `core.flag_target` | core | Flag targeting rules |
| `core.maintenance_window` | core | Maintenance windows |
| `core.remote_config` | core | Remote config values |
| `core.remote_config_history` | core | Config version history |
| `core.broadcast` | core | Broadcast messages |
| `core.broadcast_delivery` | core | Delivery tracking |
| `core.force_update_rule` | core | App version rules |
| `core.security_event` | core | Raw security events |
| `core.security_feed` | core | Aggregated security feed |
| `core.alert_rule` | core | Alert definitions |
| `core.alert_incident` | core | Alert incidents |
| `core.error_fingerprint` | core | Error grouping |
| `core.error_event` | core | Individual error occurrences |
| `core.analytics_event` | core | Raw analytics events |
| `core.analytics_daily_aggregate` | core | Daily aggregations |
| `core.analytics_segment` | core | User segments |
| `core.analytics_funnel` | core | Funnel definitions |
| `core.analytics_anomaly` | core | Detected anomalies |
| `core.moderation_queue` | core | Content moderation |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2024-10-15 | Initial release |
| 1.1 | 2024-11-01 | Added force update, security feed |
| 1.2 | 2024-12-01 | Added analytics, user 360 |

---

*For operational procedures, see [RUNBOOK.md](./RUNBOOK.md)*
*For adding features, see [ADDING_FEATURES.md](./ADDING_FEATURES.md)*