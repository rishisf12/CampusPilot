# CampusPilot — Free Tier Stack Plan

## Goal

Deliver a premium user experience at the lowest possible cost. Target: **₹67/month** (domain only).

---

## Stack Overview

| Component | Choice | Cost | Impact |
|-----------|--------|------|--------|
| **Frontend** | Vite + React + Tailwind + shadcn/ui | ₹0 | Professional look |
| **Dark mode** | CSS variables + `prefers-color-scheme` | ₹0 | Students love it |
| **Skeleton loaders** | React components with pulse animation | ₹0 | Perceived speed |
| **PWA** | `vite-plugin-pwa` + manifest.json | ₹0 | App-like feel |
| **Debounced search** | `useDeferredValue` / custom hook | ₹0 | Performance |
| **Pagination** | Supabase `.range()` cursor-based | ₹0 | Performance |
| **Auth** | Supabase Auth (Google/GitHub OAuth) | ₹0 | One-click login |
| **Database** | Supabase Postgres (free tier) | ₹0 | Reliable DB |
| **Email** | Gmail API (metadata in DB + lazy load body) | ₹0 | College emails synced daily |
| **Hosting** | Vercel (free tier) | ₹0 | Global CDN |
| **Domain** | `.app` or `.in` | ₹800/year | Professional URL |

**Total: ₹67/month — Feels premium**

---

## Implementation Checklist

### Week 1: Core UX Polish

- [ ] **Dark mode** — Tailwind `dark:` class + toggle in navbar
- [ ] **Skeleton loaders** — Replace all loading spinners with skeleton cards
- [ ] **Optimistic UI** — Show "Applied!" instantly, sync in background
- [ ] **Keyboard navigation** — Tab through job cards, Enter to open, Esc to close
- [ ] **Debounced search** — 300ms delay before querying
- [ ] **Infinite scroll** — Load 20 jobs at a time as user scrolls

### Week 2: PWA + Performance

- [ ] **PWA manifest** — App icon, name, theme color, splash screen
- [ ] **Service Worker** — Offline caching for static assets + job listings
- [ ] **Vite code splitting** — Manual chunks for vendor, UI, charts
- [ ] **Resource hints** — `preconnect`, `preload`, `prefetch` on key routes
- [ ] **Image optimization** — Compress images, use WebP, lazy load
- [ ] **Font optimization** — Self-host fonts, `font-display: swap`

### Week 3: Gmail API Integration

- [ ] **Gmail OAuth setup** — Authorize with college email account
- [ ] **Daily sync job** — Fetch new emails once/day (saves API quota)
- [ ] **Metadata in DB** — Store subject, sender, date, snippet (~1 KB/email)
- [ ] **Lazy load body** — Fetch full email content only when user opens it
- [ ] **Cache opened emails** — Reduce repeat API calls
- [ ] **Search** — Use Gmail API `q` parameter for server-side search

---

## Architecture

```
┌─────────────────────────────────────────────┐
│                  Vercel CDN                  │
│         (Global Edge Network, Free)          │
└──────────────────────┬──────────────────────┘
                       │
┌──────────────────────▼──────────────────────┐
│           Vite + React (SPA)                │
│  ┌─────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ Tailwind│ │shadcn/ui │ │  Dark Mode   │  │
│  └─────────┘ └──────────┘ └──────────────┘  │
│  ┌─────────┐ ┌──────────┐ ┌──────────────┐  │
│  │   PWA   │ │Skeletons │ │  Debounced   │  │
│  │   SW    │ │ Loaders  │ │    Search    │  │
│  └─────────┘ └──────────┘ └──────────────┘  │
│  ┌─────────────────────────────────────┐    │
│  │     Email Viewer (Lazy Load)        │    │
│  └─────────────────────────────────────┘    │
└──────────┬────────────────────┬─────────────┘
           │                    │
┌──────────▼─────────┐ ┌────────▼──────────────┐
│  Supabase (Free)   │ │    Gmail API (Free)   │
│  ┌───────────────┐ │ │  ┌─────────────────┐  │
│  │  Auth (OAuth) │ │ │  │  Daily Sync Job │  │
│  ├───────────────┤ │ │  ├─────────────────┤  │
│  │  Postgres DB  │ │ │  │  250 units/day  │  │
│  │  ~1 KB/email  │ │ │  │  ~50 emails/day │  │
│  └───────────────┘ │ │  └─────────────────┘  │
│  ┌───────────────┐ │ │                      │
│  │  Realtime     │ │ │                      │
│  │  (200 conn)   │ │ │                      │
│  └───────────────┘ │ │                      │
└────────────────────┘ └──────────────────────┘
```

---

## When to Use PostgreSQL vs pgvector

Both are **free** — pgvector is included in Supabase Postgres at no extra cost.

| Feature | Best Tool | Why |
|---------|-----------|-----|
| **Job posting storage** | PostgreSQL | Structured data, CRUD |
| **Exact search (title, company)** | PostgreSQL | Keyword match is enough |
| **Semantic search (skills, description)** | pgvector | Understands intent |
| **"Similar jobs" recommendations** | pgvector | Embedding similarity |
| **Resume-job matching** | pgvector | Semantic alignment |
| **Duplicate detection** | pgvector | Near-duplicate embeddings |
| **Location/deadline filters** | PostgreSQL | Range queries |
| **User auth, profiles, sponsors** | PostgreSQL | Relational data |
| **Email metadata** | PostgreSQL | Structured, small records |
| **Sponsored listings** | PostgreSQL | Simple relational data |

### Implementation

```sql
-- Enable pgvector (free, included in Supabase)
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column to jobs table
ALTER TABLE jobs ADD COLUMN embedding vector(384);

-- Semantic search query
SELECT * FROM jobs
ORDER BY embedding <=> '[query_embedding]'
LIMIT 10;

-- Hybrid search: keyword + semantic
SELECT * FROM jobs
WHERE title ILIKE '%python%'
ORDER BY embedding <=> '[query_embedding]'
LIMIT 10;
```

### When to Add pgvector

| Trigger | Action |
|---------|--------|
| Keyword search misses relevant results | Add semantic search |
| Need "Similar Jobs" feature | Add embedding similarity |
| Resume upload feature | Add resume-job matching |
| 1,000+ jobs with overlapping descriptions | Add duplicate detection |

---

## Cost Breakdown

| Item | Monthly | Yearly |
|------|---------|--------|
| Vercel (free) | ₹0 | ₹0 |
| Supabase (free) | ₹0 | ₹0 |
| Domain (.app/.in) | ₹67 | ₹800 |
| **Total** | **₹67** | **₹800** |

---

## Why This Works

| Benefit | How |
|---------|-----|
| **Feels premium** | Dark mode, skeletons, PWA, keyboard nav |
| **Fast** | Vercel CDN, code splitting, debounced search |
| **Reliable** | Supabase free tier handles 3K users easily |
| **Zero risk** | No bills, no downtime worries, upgrade anytime |
| **Scalable** | Clear upgrade path when triggers hit |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Lighthouse Performance | 90+ |
| Lighthouse Accessibility | 95+ |
| Time to Interactive | < 2s |
| First Contentful Paint | < 1s |
| Offline functional | Yes (PWA) |
| Monthly cost | ₹67 |
