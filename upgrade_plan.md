# CampusPilot — Upgrade Plan

## When to Upgrade (Triggers Only)

Do NOT upgrade preemptively. Upgrade **only when a trigger fires**.

---

## Upgrade Triggers

| Trigger | Upgrade To | Monthly Cost | Why |
|---------|-----------|--------------|-----|
| **5,000+ monthly active users** | Supabase Pro | +$25 (~₹2,100) | Free tier DB limits reached |
| **10,000+ jobs in DB** | Add Redis caching | +$5 (~₹415) | Query performance degrades |
| **Need realtime at scale** | Self-hosted or Paid Realtime | +$25 (~₹2,100) | 200 connection limit hit |
| **Revenue > ₹10,000/month** | Railway ($5–10) | +$5–10 (~₹415–830) | Need reliable compute for API |
| **Gmail API quota exceeded** | Google Workspace / Batch sync | ₹0 (optimize first) | 250 units/day limit hit |

---

## Upgrade Paths

### Path 1: Supabase Only Upgrade

| Current | Upgrade | Cost |
|---------|---------|------|
| Supabase Free | Supabase Pro | +$25/mo |

**When:** 5,000+ monthly active users, or DB approaching free tier limits (500MB storage, 2 GB bandwidth).

**What you get:**
- 8 GB database storage
- 250 GB bandwidth
- Daily backups
- Email support
- No connection limits

---

### Path 2: Add Redis Caching

| Current | Upgrade | Cost |
|---------|---------|------|
| No cache | Upstash Redis (free tier) or Railway Redis | ₹0–$5/mo |

**When:** 10,000+ jobs in DB, or search queries getting slow (>500ms response).

**What you get:**
- Sub-10ms cache lookups
- Reduced DB load
- Faster search responses

---

### Path 3: Realtime at Scale

| Current | Upgrade | Cost |
|---------|---------|------|
| Supabase Realtime Free (200 conn) | Supabase Pro Realtime or Self-hosted | +$25/mo or ₹0 (self-hosted) |

**When:** Realtime connections approaching 200 concurrent.

**What you get:**
- Unlimited concurrent connections
- No message rate limits

---

### Path 4: Railway Compute

| Current | Upgrade | Cost |
|---------|---------|------|
| No backend hosting | Railway $5–10/mo | $5–10/mo |

**When:** Revenue > ₹10,000/month, or need reliable API hosting.

**What you get:**
- Dedicated compute
- Auto-scaling
- Custom domains
- Monitoring

---

### Path 5: Gmail API Quota Management

| Current | Approach | Cost |
|---------|----------|------|
| Gmail API Free (250 units/day) | Optimize: batch sync, cache, metadata only | ₹0 |

**When:** Approaching 250 API units/day (~50 emails/day).

**Optimization strategies (try these first):**
- Batch sync once/day instead of on-demand fetching
- Store only metadata in DB (~1 KB/email) and lazy-load body
- Cache opened emails to avoid repeat API calls
- Use `messages.list` (5 units) instead of `messages.get` (5 units) when possible
- Strip HTML to plain text before storing

**If still exceeding quota:**
- Apply for Google Workspace (paid) — custom quota requests
- Or reduce sync frequency to every 2–3 days

---

## Revenue vs Cost Analysis

| Monthly Revenue | Hosting Cost | Net to Jagrati |
|-----------------|--------------|----------------|
| ₹0–₹10,000 | ₹0 (free tier) | ₹0–₹10,000 |
| ₹10,000–₹15,000 | ₹415 (Railway $5) | ₹9,585–₹14,585 |
| ₹15,000–₹25,000 | ₹2,515 (Railway + Supabase Pro) | ₹12,485–₹22,485 |
| ₹25,000+ | ₹4,615 (Full stack) | ₹20,385+ |

---

## Upgrade Decision Tree

```
Is revenue > ₹10,000/month?
├── NO → Stay on free tier
└── YES → Do you need reliable API hosting?
    ├── NO → Stay on free tier
    └── YES → Add Railway ($5/mo)
        └── Is DB > 5,000 monthly active users?
            ├── NO → Done
            └── YES → Upgrade Supabase Pro ($25/mo)
                └── Are queries slow (>500ms)?
                    ├── NO → Done
                    └── YES → Add Redis ($5/mo)
```

---

## Pre-Upgrade Checklist

Before upgrading, confirm:

- [ ] Trigger metric actually fired (not just a guess)
- [ ] Current free tier is actually failing (errors, slow queries, downtime)
- [ ] Revenue can cover the new cost
- [ ] You've optimized what you can (indexes, caching, code splitting)
- [ ] The upgrade solves a real problem, not a theoretical one

---

## Cost Projection by User Growth

| Monthly Users | Stack | Monthly Cost | Yearly Cost |
|---------------|-------|--------------|-------------|
| 1,000 | Free tier | ₹67 | ₹800 |
| 3,000 | Free tier | ₹67 | ₹800 |
| 5,000 | + Supabase Pro | ₹2,167 | ₹26,000 |
| 10,000 | + Redis | ₹2,582 | ₹31,000 |
| 20,000 | + Railway | ₹2,997 | ₹36,000 |
| 50,000 | Full stack | ₹4,615 | ₹55,400 |

---

## Summary

| Principle | Rule |
|-----------|------|
| **Default** | Free tier until trigger fires |
| **Upgrade only when** | Trigger metric confirmed + revenue covers cost |
| **Never upgrade** | Preemptively or for "future-proofing" |
| **Always optimize** | Code, indexes, caching before spending |
