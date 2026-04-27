# SevaSetu — Full Codebase Review Report

> **Date:** 27 April 2026  
> **Reviewer:** Automated Deep Review  
> **Scope:** Backend (FastAPI/Python), Frontend (Next.js/TypeScript), Database (PostgreSQL + pgvector), Docker, Environment, Tests, Services, Security

---

## 1. Project Overview

**SevaSetu** ("Bridge of Service") is an AI-powered Smart Resource Allocation Platform for NGOs. It matches community humanitarian needs with qualified volunteers across India using a multi-signal scoring engine backed by Google Gemini AI.

### Core Value Proposition
- **Multi-channel need intake:** Dashboard, WhatsApp, Google Forms, CSV upload, offline/disaster mode
- **5-Signal AI Matching Engine:** Skill embeddings, tag overlap, geo-proximity, urgency, availability
- **3-Tier AI Fallback:** Gemini API → Gemma 4 local → Keyword rules
- **Self-improving weights:** Hybrid weight calibrator that learns from field feedback
- **Disaster Mode:** Automatic anomaly detection triggers mass volunteer mobilization

---

## 2. Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (Next.js 16)                     │
│  React 19 · TypeScript · Tailwind 4 · Framer Motion · SWR  │
│  Pages: Landing, Dashboard, Needs, Volunteers, Chat         │
└───────────────────────┬─────────────────────────────────────┘
                        │  REST + WebSocket
┌───────────────────────▼─────────────────────────────────────┐
│                   BACKEND (FastAPI 0.115)                    │
│  Python 3.12 · Async · Pydantic v2 · APScheduler            │
│  Routes: needs, volunteers, matching, dashboard, ingestion,  │
│          system, chat                                        │
│  Services: gemini, gemma, embedding, matching_engine,        │
│            weight_calibrator, disaster, briefing, clustering, │
│            offline_queue, skill_normalizer, feedback_analyzer │
│  Middleware: Firebase Auth · Rate Limiting · CORS · Logging  │
└───────────────────────┬─────────────────────────────────────┘
                        │  asyncpg
┌───────────────────────▼─────────────────────────────────────┐
│              DATABASE (PostgreSQL 16 + pgvector)             │
│  Tables: needs, volunteers, assignments, organizations,      │
│          need_clusters, gemini_calls                          │
│  Extensions: vector (384-dim), uuid-ossp                     │
│  Migrations: Alembic                                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Backend Review

### 3.1 Entry Point — `main.py` (361 lines)

| Aspect | Status | Notes |
|--------|--------|-------|
| Lifespan management | ✅ Good | Proper startup/shutdown with DB init, scheduler, offline queue |
| Middleware ordering | ✅ Correct | CORS → Auth → Logging → Size Limit (outermost-first for CORS) |
| Scheduled jobs | ✅ Good | Urgency decay (1h), clustering (6h), briefing (6h) |
| Health check | ✅ Comprehensive | Checks DB, Gemini, embeddings, Maps, Gemma, offline queue, scheduler |
| Request logging | ✅ Present | Timing + status code logged per request |
| Request size limit | ✅ 2MB cap | Prevents DoS via large payloads |

**Issues Found:**
- ⚠️ `datetime.utcnow()` is deprecated in Python 3.12+. Should use `datetime.now(timezone.utc)` throughout the codebase (appears in ~15+ locations).
- ⚠️ The `_sync_job_wrapper` uses `asyncio.get_event_loop()` which is deprecated. Should use `asyncio.get_running_loop()` or restructure for APScheduler's async support.

### 3.2 Configuration — `config.py` (83 lines)

| Setting Category | Count | Notes |
|-----------------|-------|-------|
| Database | 1 | PostgreSQL with asyncpg |
| Google AI | 2 | Gemini API key, Maps API key |
| Firebase | 2 | Credentials path, dev bypass flag |
| Feature Flags | 4 | WhatsApp, Sheets sync, disaster thresholds |
| Matching | 7 | Weight defaults, search radius, max candidates |
| Urgency | 4 | Decay rate, tier thresholds |
| Dedup | 2 | Cosine threshold (0.90), window (7 days) |

✅ Well-structured with `pydantic-settings`. All settings have sensible defaults.

### 3.3 Database Layer — `database.py` (84 lines)

- ✅ Async engine with connection pooling (10 pool, 20 overflow)
- ✅ `pool_pre_ping` for stale connection detection
- ✅ `pool_recycle=300` prevents long-lived connections
- ✅ Proper dependency injection via `get_db()` with rollback on exception
- ✅ Auto-creates pgvector + uuid-ossp extensions on init

### 3.4 ORM Models — `db_models.py` (219 lines)

| Model | Fields | Indexes | Notes |
|-------|--------|---------|-------|
| **Need** | 20 | 7 | Full lifecycle: new → matched → assigned → in_progress → completed |
| **Volunteer** | 16 | 3 | Skills, languages, reliability tracking, 384-dim embedding |
| **Assignment** | 10 | 3 | Bridges need↔volunteer with score breakdown + feedback |
| **Organization** | 7 | 0 | NGO/government body with sheet sync |
| **NeedCluster** | 7 | 0 | DBSCAN clustering results |
| **GeminiCall** | 9 | 3 | API usage tracking for billing |

**Issues Found:**
- ⚠️ `Organization` model has no indexes — queries on `name` or `sheet_id` will be slow at scale.
- ⚠️ `NeedCluster` has no index on `need_type` or `created_at`.
- ⚠️ `default=[]` on ARRAY columns is a mutable default — should use `default=list` or `server_default`.

### 3.5 Pydantic Schemas — `schemas.py` (298 lines)

- ✅ 16 well-typed request/response schemas with validation
- ✅ Regex patterns on enum fields (`need_type`, `status`, `message_type`)
- ✅ `ConfigDict(from_attributes=True)` for ORM→schema conversion
- ✅ JSON schema examples for API docs

### 3.6 API Routes

| Route File | Endpoints | Lines | Key Features |
|-----------|-----------|-------|--------------|
| `need_routes.py` | 6 | 206 | CRUD + stats + SHA-256 dedup |
| `volunteer_routes.py` | 5 | 121 | Registration, profile, impact tracking |
| `match_routes.py` | 8 | 603 | 2-phase matching (instant + LLM), assignments, feedback loop |
| `dashboard_routes.py` | 5 | 306 | Stats, heatmap, activity feed, deserts, volunteer locations |
| `ingestion_routes.py` | 10 | 640 | WhatsApp, Forms, CSV, offline, 3-tier dedup |
| `chat_routes.py` | 1 | 140 | WebSocket RAG chat with vector search |
| `system_routes.py` | 7 | 159 | Urgency decay, clustering, briefings, cache monitoring |

**Highlights:**
- ✅ Match routes use `SELECT ... FOR UPDATE` to prevent double-booking race conditions
- ✅ 3-tier deduplication: hash → structural (type+geo) → semantic (cosine > 0.90)
- ✅ Feedback loop: field outcomes drive weight calibrator self-improvement
- ✅ Offline ingestion with Gemma triage and background sync

**Issues Found:**
- ⚠️ `match_routes.py` line 358: docstring placed after variable assignment — cosmetic but unusual
- ⚠️ `ingestion_routes.py`: The `_ingest_text` function is 140+ lines — should be split into smaller composable steps
- ⚠️ `chat_routes.py`: WebSocket loads ALL active needs into memory for vector search — won't scale past ~10K needs. Should use pgvector `ORDER BY embedding <=> query LIMIT 5` directly.
- ⚠️ `dashboard_routes.py`: Desert detection runs 20 sequential DB queries (one per population center) — should batch into a single query.

### 3.7 Services (20 files)

| Service | Lines | Purpose | AI Tier |
|---------|-------|---------|---------|
| `gemini_service.py` | 682 | Need extraction, dispatch briefs, match validation | Tier 1 |
| `gemma_service.py` | 325 | Local Gemma 4 inference (zero cost) | Tier 2 |
| `matching_engine.py` | 272 | 5-signal scoring with dynamic weights | Core |
| `weight_calibrator.py` | 463 | Hybrid static+LLM weight evolution | Core |
| `embedding_service.py` | 95 | MiniLM-L12 384-dim multilingual embeddings | Core |
| `skill_normalizer.py` | ~300 | Synonym resolution for skill matching | Core |
| `disaster_service.py` | 206 | Anomaly detection + mass mobilization | Critical |
| `briefing_service.py` | ~300 | Regional coordinator briefings | Analytics |
| `clustering_service.py` | ~130 | DBSCAN need clustering | Analytics |
| `feedback_analyzer.py` | ~200 | Structured signal extraction from feedback | Learning |
| `offline_queue.py` | ~400 | Disk-backed offline report queue | Resilience |
| `notification_service.py` | ~170 | Firebase Cloud Messaging | Comms |
| `geocoding_service.py` | ~170 | Google Maps + 14-city offline fallback | Geo |
| `translation_service.py` | ~180 | Google Cloud Translation v3 | i18n |
| `speech_service.py` | ~200 | Google Cloud Speech-to-Text | Ingestion |
| `urgency_service.py` | ~160 | Time-based urgency decay | Core |
| `llm_cache.py` | ~150 | In-memory LLM response cache (TTL-based) | Performance |
| `match_cache.py` | ~90 | 30-min match explanation cache | Performance |
| `sheets_service.py` | ~210 | Google Sheets v4 sync | Integration |

**Architecture Strengths:**
- ✅ Circuit breaker pattern on Gemini (5 failures → 5min cooldown → auto-reset)
- ✅ 3-tier AI fallback (Gemini → Gemma → Keywords) ensures zero downtime
- ✅ Weight calibrator is genuinely self-improving: LLM adjustments that recur ≥5 times update the static map permanently
- ✅ Learning state persists to disk (`data/learning_state.json`, `data/learned_weights.json`)
- ✅ Bounded memory: sliding window of 10 entries per context key (~50KB max)

**Issues Found:**
- 🔴 **`gemini_service.py` line 121**: Logs model as `"gemini-1.5-flash"` but actually uses `"gemini-2.5-flash"` — billing tracking mismatch.
- ⚠️ `gemma_service.py`: `is_available` property triggers `_try_load()` which downloads a 4B param model — dangerous in property access. Should be explicit `ensure_loaded()`.
- ⚠️ `weight_calibrator.py`: Learning threshold of 5 is relatively low. Could cause premature static map updates from noisy LLM responses.
- ⚠️ `embedding_service.py`: Fallback hash-based encoding produces semantically meaningless vectors — fine for dev but should log a warning when used in production scoring.

### 3.8 Middleware

| Middleware | Purpose | Notes |
|-----------|---------|-------|
| **Firebase Auth** | Token validation on POST/PATCH/DELETE | ✅ Dev bypass mode, proper CORS interaction |
| **Rate Limiting** | Per-IP via slowapi | ✅ 3 tiers: 100/min default, 30/min ingestion, 10/min system |
| **CORS** | Cross-origin for frontend | ✅ Allows localhost:3000/3001 |
| **Request Logging** | Timing + status | ✅ Per-request |
| **Size Limiting** | 2MB body cap | ✅ Prevents payload abuse |

---

## 4. Frontend Review

### 4.1 Technology Stack

| Technology | Version | Purpose |
|-----------|---------|---------|
| Next.js | 16.2.4 | React framework (App Router) |
| React | 19.2.4 | UI library |
| TypeScript | 5.x | Type safety |
| Tailwind CSS | 4.x | Utility CSS (used in layout only) |
| Framer Motion | 12.38 | Animations |
| Recharts | 3.8.1 | Data visualization |
| SWR | 2.4.1 | Data fetching (available but underutilized) |
| Lucide React | 1.11 | Icons |

### 4.2 Page Structure

| Page | File | Lines | Features |
|------|------|-------|----------|
| **Landing** | `app/page.tsx` | 211 | Hero, live stats strip, how-it-works, CTA |
| **Dashboard** | `app/dashboard/page.tsx` | 207 | Stats grid, heatmap, need deserts, needs by type, chat panel |
| **Needs List** | `app/needs/page.tsx` | 175 | Filterable grid with pagination, search |
| **New Need** | `app/needs/new/page.tsx` | ~300 | Multi-field form for need submission |
| **Volunteers** | `app/volunteers/page.tsx` | 141 | Filterable list with skill search |

### 4.3 API Client — `lib/api.ts` (382 lines)

- ✅ Fully typed with 20+ TypeScript interfaces
- ✅ Centralized `apiFetch<T>` wrapper with error handling
- ✅ Client-side LLM explanation cache (`Map`)
- ✅ WebSocket factory for chat
- ✅ Covers all backend endpoints

**Issues Found:**
- ⚠️ `updateAssignmentStatus` sends status/rating/feedback as query params but the backend expects a JSON body — **this is a bug** that would cause 422 errors.
- ⚠️ No auth token attachment in `apiFetch` — all POST/PATCH/DELETE will fail when Firebase auth is enabled in production.
- ⚠️ No request retry logic or error boundary integration.

### 4.4 Components

| Component | Lines | Purpose |
|-----------|-------|---------|
| **MatchCard** | 325 | Full match display with score bars, AI validation button, dispatch brief, assignment CTA |

**Issues Found:**
- ⚠️ The `app/` directory has pages but references components like `NeedCard`, `VolunteerCard`, `StatsCard`, `ChatPanel`, `HeatMap`, `NeedDesertOverlay`, `EmptyState`, `LoadingBar` and utility modules (`lib/utils`, `lib/animations`) that **don't exist in the repository**. These imports will cause build failures.
- ⚠️ The `src/app/` directory still has the default Next.js boilerplate (`page.tsx` with "Deploy Now" template) — this conflicts with `app/page.tsx`.
- ⚠️ Path alias `@/*` maps to `./src/*` in tsconfig, but most app code lives in `./app/` — potential import resolution issues.

---

## 5. Environment & Configuration Review

### 5.1 Backend `.env`

| Variable | Value | Risk |
|----------|-------|------|
| `DATABASE_URL` | `postgresql+asyncpg://sevasetu:sevasetu_dev_2024@localhost:5432/sevasetu` | ⚠️ Port 5432 but docker-compose maps to 5433 — **mismatch** |
| `GEMINI_API_KEY` | `AIzaSyBR...` | 🔴 **Real API key committed to repo** |
| `GOOGLE_MAPS_API_KEY` | `AIzaSyD8...` | 🔴 **Real API key committed to repo** |
| `FIREBASE_CREDENTIALS_PATH` | `/Users/ayushgourav/...` | ⚠️ Hardcoded macOS absolute path — won't work on other machines |
| `FIREBASE_DEV_BYPASS` | `true` | ✅ Expected for dev |
| `GOOGLE_APPLICATION_CREDENTIALS` | `/Users/ayushgourav/...` | ⚠️ Same hardcoded path issue |

**Critical Security Issues:**
- 🔴 **API keys are committed to the repo.** The `.gitignore` blocks `.env` but the file already exists. If this repo is public or ever was, these keys are compromised. **Rotate immediately.**
- 🔴 `firebase-service-account.json` (2.3KB) exists in the backend directory. Although `.gitignore` blocks `*-service-account*.json`, it should be verified it was never committed.

### 5.2 Database Port Mismatch

- `docker-compose.yml` maps port **5433:5432**
- `backend/.env` uses port **5432**
- `backend/app/config.py` default uses port **5433**

The `.env` file overrides the config default, pointing to the wrong port. This would cause connection failures unless PostgreSQL is also running natively on port 5432.

### 5.3 `.gitignore` Review

✅ Properly configured for:
- Environment files (`.env`, `.env.*`)
- Firebase credentials (`*-service-account*.json`)
- Python artifacts (`__pycache__`, `*.pyc`)
- Node modules, `.next`, build artifacts
- IDE files (`.vscode`, `.idea`)
- OS files (`.DS_Store`)

---

## 6. Docker & Infrastructure

### 6.1 `docker-compose.yml`

- ✅ Uses `pgvector/pgvector:pg16` image with health check
- ✅ Persistent volume for data
- ✅ Init scripts for extensions
- ⚠️ Only defines the database service — no backend or frontend containers
- ⚠️ No `docker-compose.override.yml` for dev vs prod

### 6.2 Backend `Dockerfile`

- ✅ Python 3.12-slim base
- ✅ System deps for psycopg2/asyncpg
- ✅ Proper PYTHONPATH setting
- ⚠️ No multi-stage build — production image includes build tools
- ⚠️ No `.dockerignore` — could copy unnecessary files
- ⚠️ `.env` file not copied (good for security, but needs env vars injected at runtime)

---

## 7. Testing

### 7.1 Test Suite (10 test files)

| Test File | Lines | Category |
|-----------|-------|----------|
| `test_integration_api.py` | ~900 | API endpoint integration |
| `test_e2e_lifecycle.py` | ~780 | Full need→match→assign→feedback lifecycle |
| `test_ingestion_all_channels.py` | ~750 | WhatsApp, Forms, CSV, offline |
| `test_security_adversarial.py` | ~800 | XSS, injection, rate limiting |
| `test_ai_tiers.py` | ~700 | Gemini/Gemma/fallback tier testing |
| `test_feedback_loop.py` | ~780 | Weight calibrator learning loop |
| `test_deduplication.py` | ~700 | 3-tier dedup verification |
| `test_matching_stress.py` | ~720 | Volume/load testing |
| `test_dashboard_analytics.py` | ~740 | Dashboard stats + heatmap |
| `test_unit_services.py` | ~460 | Service-level unit tests |

- ✅ Comprehensive coverage with 10 dedicated test files
- ✅ `conftest.py` with proper async fixtures and test DB setup
- ✅ Pytest markers: `unit`, `integration`, `multilingual`, `stress`, `ai`, `e2e`, `live`
- ✅ Security/adversarial tests (rare and valuable)

### 7.2 Seed Data

- `scripts/seed_production.py` (25KB) — Production-realistic seed script with Indian locations, volunteer profiles, and need scenarios.

---

## 8. Security Assessment

| Category | Finding | Severity |
|----------|---------|----------|
| API Keys in `.env` | Real Gemini & Maps keys committed | 🔴 Critical |
| Firebase Service Account | JSON file in repo (gitignored) | ⚠️ High |
| Auth Bypass | `FIREBASE_DEV_BYPASS=true` in `.env` | ⚠️ Medium (dev only) |
| Rate Limiting | ✅ 3-tier rate limiting in place | ✅ Good |
| Request Size | ✅ 2MB body limit | ✅ Good |
| Input Sanitization | ✅ Control character stripping on need creation | ✅ Good |
| SQL Injection | ✅ SQLAlchemy parameterized queries | ✅ Good |
| CORS | ✅ Restricted to specific origins | ✅ Good |
| Race Conditions | ✅ `FOR UPDATE` locks on assignment | ✅ Good |
| Content Dedup | ✅ SHA-256 hash + cosine similarity | ✅ Good |

---

## 9. Code Quality Summary

### Strengths
1. **Exceptional architecture:** 3-tier AI fallback with circuit breaker is production-grade
2. **Self-improving system:** Weight calibrator genuinely learns from field outcomes
3. **Comprehensive testing:** 10 test files covering unit, integration, e2e, security, stress
4. **Robust ingestion:** 6+ channels with 3-tier deduplication
5. **Offline resilience:** Disk-backed queue with Gemma triage during outages
6. **Well-documented code:** Extensive docstrings and inline comments throughout
7. **Type safety:** Pydantic v2 schemas + TypeScript interfaces
8. **Operational health:** Detailed health checks, Gemini call logging, cache monitoring

### Issues to Address

| Priority | Issue | Location |
|----------|-------|----------|
| 🔴 Critical | API keys committed to `.env` | `backend/.env` |
| 🔴 Critical | Missing frontend components (build will fail) | `app/components/` |
| 🔴 High | Database port mismatch (`.env` says 5432, docker maps 5433) | `backend/.env` line 5 |
| 🔴 High | Gemini model name mismatch in billing log | `gemini_service.py:121` |
| ⚠️ Medium | `updateAssignmentStatus` sends body as query params | `lib/api.ts:334` |
| ⚠️ Medium | No auth token in frontend API client | `lib/api.ts` |
| ⚠️ Medium | Chat loads all needs into memory for vector search | `chat_routes.py:46` |
| ⚠️ Medium | `datetime.utcnow()` deprecated (15+ occurrences) | Throughout backend |
| ⚠️ Low | Default Next.js boilerplate in `src/app/page.tsx` | `frontend/src/app/page.tsx` |
| ⚠️ Low | Mutable default `default=[]` on ARRAY columns | `db_models.py` |
| ⚠️ Low | Missing indexes on Organization and NeedCluster | `db_models.py` |

---

## 10. File & Line Count Summary

### Backend
| Category | Files | Total Lines (approx) |
|----------|-------|---------------------|
| Core (main, config, db) | 3 | ~530 |
| Models + Schemas | 3 | ~520 |
| Routes | 7 | ~2,270 |
| Services | 20 | ~5,600 |
| Middleware | 3 | ~260 |
| Tests | 11 | ~7,300 |
| Scripts | 1 | ~750 |
| **Backend Total** | **48** | **~17,230** |

### Frontend
| Category | Files | Total Lines (approx) |
|----------|-------|---------------------|
| Pages | 5 | ~1,000 |
| Components | 1 | ~325 |
| API Client | 1 | ~382 |
| Config | 4 | ~100 |
| **Frontend Total** | **11** | **~1,807** |

### **Grand Total: ~19,000 lines of code**

---

## 11. Recommendations

### Immediate Actions
1. **Rotate all API keys** — Gemini, Google Maps, Firebase service account
2. **Create `.env.example`** with placeholder values; remove real `.env` from any commits
3. **Fix the database port** in `.env` (change 5432 → 5433 to match docker-compose)
4. **Create the missing frontend components** (NeedCard, StatsCard, ChatPanel, HeatMap, etc.) or consolidate into the `app/components/` directory

### Short-Term
5. Fix `updateAssignmentStatus` in `lib/api.ts` to send JSON body instead of query params
6. Add Firebase auth token injection to the frontend API client
7. Replace `datetime.utcnow()` with `datetime.now(timezone.utc)` globally
8. Fix Gemini model name in billing logger (`gemini_service.py:121`)
9. Use pgvector `ORDER BY <=>` in chat for scalable vector search

### Long-Term
10. Add frontend containers to `docker-compose.yml` for full-stack local dev
11. Implement proper error boundaries in the React frontend
12. Add a `.dockerignore` file
13. Consider Redis for rate limiting and caching in production (config already supports it)
14. Remove the default Next.js boilerplate from `src/app/page.tsx`

---

*End of Report*
