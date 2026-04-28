# SevaSetu — Frontend Technical Report

> **Date:** 27 April 2026 · **Scope:** Every file in `frontend/`

---

## 1. Technology Stack

| Package | Version | Role |
|---------|---------|------|
| Next.js | 16.2.4 | App Router framework |
| React | 19.2.4 | UI runtime |
| TypeScript | ^5 | Type safety |
| Tailwind CSS | ^4 | Utility CSS (only in `src/app/`) |
| Deck.gl | ^9.0.0 | High-performance WebGL mapping |
| MapLibre GL | ^4.0.0 | Vector map base tiles |
| Framer Motion | ^12.38 | Page transitions + micro-animations |
| Recharts | ^3.8.1 | Charts (installed but **unused**) |
| SWR | ^2.4.1 | Data fetching (installed but **unused**) |
| Lucide React | ^1.11 | Icons (installed but **unused**) |
| clsx + tailwind-merge | latest | Class merging (installed but **unused**) |

---

## 2. File Inventory (26 files)

```
frontend/
├── package.json              # Dependencies + scripts
├── tsconfig.json             # Path alias: @/* → ./*
├── next.config.ts            # Empty Next config
├── next-env.d.ts             # Auto-generated types
│
├── app/                      # ← ACTIVE App Router
│   ├── layout.tsx            # Root layout (html/body/navbar)
│   ├── page.tsx              # Landing page (hero + stats + CTA)
│   ├── dashboard/page.tsx    # Live dashboard (stats + map + chat)
│   ├── needs/page.tsx        # Needs listing (filterable grid)
│   ├── needs/new/page.tsx    # Submit new need (form)
│   ├── volunteers/page.tsx   # Volunteers listing (filterable grid)
│   └── components/
│       ├── ChatPanel.tsx     # WebSocket RAG chat panel
│       ├── EmptyState.tsx    # Empty filter result state
│       ├── HeatMap.tsx       # Interactive Deck.gl + MapLibre map
│       ├── LoadingBar.tsx    # Animated top progress bar
│       ├── MatchCard.tsx     # Volunteer match + AI validation
│       ├── NeedCard.tsx      # Need card for grid views
│       ├── NeedDesertOverlay.tsx # Under-reported zone list
│       ├── StatsCard.tsx     # Dashboard KPI metric card
│       └── VolunteerCard.tsx # Volunteer profile card
│
├── lib/                      # Shared logic
│   ├── api.ts                # Typed API client (382 lines)
│   ├── utils.ts              # Formatting helpers (62 lines)
│   └── animations.ts         # Framer Motion presets (31 lines)
│
└── src/app/                  # ← DEAD CODE (Next.js boilerplate)
    ├── layout.tsx            # Default "Create Next App" layout
    ├── page.tsx              # Default template page
    └── globals.css           # Tailwind import + CSS vars
```

---

## 3. Page-by-Page Breakdown

### 3.1 Root Layout — `app/layout.tsx` (74 lines)

| Aspect | Detail |
|--------|--------|
| **Fonts** | Google Fonts: Outfit (headings) + Inter (body) via `next/font/google` |
| **Navbar** | Persistent top bar: logo + Dashboard / Needs / Volunteers links |
| **Metadata** | Title: "SevaSetu — AI-Powered Resource Allocation" |
| **Styling** | Inline styles, `antialiased`, `#1C1917` text on `#ffffff` bg |

**Issues:**
- ⚠️ Uses `<a href>` instead of Next.js `<Link>`. Every navigation does a full page reload instead of client-side routing.
- ⚠️ No active-link highlighting — user can't tell which page they're on.
- ⚠️ No mobile hamburger menu — navbar items will overflow on small screens.
- ⚠️ Fonts loaded via `<link>` tag instead of `next/font` — loses automatic font optimization. (RESOLVED: Now using next/font)

---

### 3.2 Landing Page — `app/page.tsx` (211 lines)

| Section | Content |
|---------|---------|
| **Hero** | Full-viewport headline + subtitle + 2 CTAs ("Report a Need", "Join as Volunteer") |
| **Stats Strip** | 4 live KPIs from `/api/dashboard/stats`: Needs Tracked, Volunteers Matched, Active Volunteers, Critical Now |
| **How It Works** | 3-step explainer: Report → Match → Resolve |
| **CTA** | "Open Dashboard →" link |
| **Footer** | Logo + nav links + tagline |

**Data Flow:** `fetchDashboardStats()` on mount → populates stats strip. Graceful `—` fallback if backend is down.

**Issues:**
- ⚠️ `btn-primary` / `btn-secondary` classes defined in `<style>` tag inside the component — not reusable across other pages.
- ⚠️ Footer duplicates navbar links — could share a config array.

---

### 3.3 Dashboard — `app/dashboard/page.tsx` (207 lines)

| Section | Data Source | Component |
|---------|------------|-----------|
| Stats Grid (6 cards) | `GET /api/dashboard/stats` | `<StatsCard>` |
| Needs Heatmap | `GET /api/dashboard/heatmap` | `<HeatMap>` |
| Need Deserts | `GET /api/dashboard/deserts` | `<NeedDesertOverlay>` |
| Needs by Type (bar chart) | Stats `.needs_by_type` | Inline Framer Motion bars |
| Volunteer Overlay | `GET /api/dashboard/volunteer-locations` | Toggle checkbox on map |
| Chat Panel | `WS /ws/chat` | `<ChatPanel>` (slide-out) |

**Data Flow:** 4 parallel fetches on mount via `Promise.all()`. All have `.catch(() => [])` fallbacks.

**Issues:**
- ⚠️ No auto-refresh / polling — dashboard is static after initial load. Should use SWR or `setInterval` for live updates.
- ⚠️ `LoadingBar` shows until ALL 4 fetches complete — slow API blocks the whole page.
- ⚠️ Responsive breakpoints defined in `<style>` tag — should be in a shared CSS file.

---

### 3.4 Needs List — `app/needs/page.tsx` (175 lines)

| Feature | Implementation |
|---------|---------------|
| **Filters** | 3 dropdowns: Type (7 options), Status (5), Urgency (4) |
| **Search** | Text input + Enter/button trigger |
| **Pagination** | "Load more" infinite scroll pattern |
| **Grid** | `auto-fill, minmax(320px, 1fr)` responsive grid |
| **Cards** | Staggered Framer Motion entry animation |

**Data Flow:** `fetchNeeds({ type, status, urgency, search, page, page_size: 18 })` — re-fetches on filter change with `reset=true`.

**Issues:**
- ⚠️ Appends to array on "Load more" but re-fetches from page 1 on filter change — could cause duplicate entries if user loads more then changes filters quickly.
- ⚠️ `page` state and filter resets are in separate `useEffect` hooks — timing-dependent logic.

---

### 3.5 Submit Need — `app/needs/new/page.tsx` (259 lines)

| Field | Type | Validation |
|-------|------|------------|
| Title * | text input | Required, trimmed |
| Description * | textarea (5 rows) | Required, trimmed |
| Need Type | select (7 options) | Default: HEALTHCARE |
| Location | text input | Optional |
| Urgency | range slider (0–1) | Live label: Low/Moderate/High/Critical |
| Affected Count | number input | Optional |
| Required Skills | tag input (Enter/comma to add) | Dedup, removable pills |

**Data Flow:** `createNeed(payload)` → on success, `router.push(/needs/{id})`.

**Strengths:**
- ✅ Urgency slider with live color + label feedback.
- ✅ Skills tag input with keyboard support (Enter + comma).
- ✅ Focus/blur border color transitions.

**Issues:**
- ⚠️ No client-side validation beyond empty check — could submit urgency=0 or negative affected count.
- ⚠️ On submit error, `setSubmitting(false)` only runs in catch — success path never resets (acceptable since it navigates away).
- ⚠️ No "Back" or "Cancel" button.

---

### 3.6 Volunteers List — `app/volunteers/page.tsx` (141 lines)

| Feature | Implementation |
|---------|---------------|
| **Filters** | Status dropdown + skill text filter |
| **Grid** | `auto-fill, minmax(300px, 1fr)` |
| **Register CTA** | "Register New" button → `/volunteers/register` |
| **Pagination** | "Load more" button |

**Issues:**
- ⚠️ `/volunteers/register` page **does not exist** — clicking "Register New" will 404.
- ⚠️ `fetchVolunteers()` returns `VolunteerResponse[]` (flat array) — no `total` count for proper pagination end detection. Uses `length >= PAGE_SIZE * page` heuristic.

---

## 4. Component-by-Component Breakdown

### 4.1 MatchCard (325 lines) — Most Complex Component

| Feature | Detail |
|---------|--------|
| Score bars | 5 animated signal bars (skill_embedding, skill_tags, geo, urgency, availability) |
| AI Validation | "🤖 Validate with AI" button → `fetchMatchExplanation()` on-demand |
| AI Verdict | Color-coded panel (green/yellow/red) with per-signal explanations |
| Dispatch Brief | Collapsible blockquote with volunteer instructions |
| Assignment CTA | "Assign This Volunteer" → `createAssignment()` with row-lock |
| Loading states | Spinner animation for AI validation, disabled button during assignment |

**Data Flow:**
1. Initial render: rule-based scores (instant)
2. User clicks "Validate with AI" → `GET /api/needs/{id}/matches/{vid}/explain`
3. LLM response populates verdict panel + updates score
4. "Assign" → `POST /api/assignments` with cleaned score_breakdown

**Issues:**
- ⚠️ `score_breakdown` cleanup strips `weights_used` (a `Record<string, number>`) since it checks `typeof v === 'number'` — but `weights_used` is an object. This is actually **correct behavior** (prevents 422), but the intent is unclear without a comment.
- ⚠️ Client-side LLM cache (`_explainCache` in `api.ts`) never invalidates — stale if need/volunteer data changes.

---

### 4.2 ChatPanel (143 lines)

| Feature | Detail |
|---------|--------|
| Connection | `createChatWebSocket()` → `ws://localhost:8000/ws/chat` |
| Messages | Bubbles: user (orange, right) / assistant (gray, left) |
| Status | Green/red connection indicator |
| UX | Auto-scroll to bottom, Enter to send |

**Issues:**
- ⚠️ WebSocket reconnects on every open/close toggle — no connection persistence.
- ⚠️ Messages are lost when panel closes (state resets).
- ⚠️ No loading indicator while waiting for AI response.

---

### 4.3 HeatMap (170 lines)

| Feature | Detail |
|---------|--------|
| Base Map | MapLibre with Carto Positron vector tiles |
| Needs Layer | `ScatterplotLayer` mapped to geo-coordinates |
| Pulse Layer | Animated radar pulse around critical needs |
| Tooltips | Glassmorphic hover tooltips with data details |
| Interactivity | Smooth `FlyToInterpolator` camera zoom on click |

**Status:**
- ✅ Beautifully upgraded to Deck.gl, resolving previous issues with overlapping dots and lack of map context.

---

### 4.4 Other Components

| Component | Lines | Purpose | Notes |
|-----------|-------|---------|-------|
| **StatsCard** | 37 | Animated KPI number + label | ✅ Clean, uses Framer Motion fade-in |
| **NeedCard** | 99 | Need tile with urgency pill, type, location, time | ✅ Hover border effect, line-clamped text |
| **VolunteerCard** | 80 | Profile with initials avatar, skills pills, reliability bar | ✅ Status indicator (🟢🟡⚪) |
| **EmptyState** | 37 | Centered 📭 icon + message + optional CTA | ✅ Simple and effective |
| **LoadingBar** | 25 | Fixed top progress bar with CSS animation | ✅ Lightweight |
| **NeedDesertOverlay** | 53 | Grid of under-reported zones | ✅ Auto-hides when no data |

---

## 5. API Client — `lib/api.ts` (382 lines)

### 5.1 Architecture

```
apiFetch<T>(path, init?)
  → fetch(BASE + path, { headers, ...init })
  → if !ok: throw Error(detail)
  → if 204: return undefined
  → return res.json()
```

### 5.2 TypeScript Interfaces (20 types)

| Interface | Fields | Used By |
|-----------|--------|---------|
| `NeedResponse` | 18 | NeedCard, needs page |
| `NeedListResponse` | 4 | Paginated needs |
| `NeedCreate` | 12 | Submit form |
| `VolunteerResponse` | 15 | VolunteerCard |
| `VolunteerRegister` | 9 | Registration form |
| `MatchResult` | 6 | MatchCard |
| `ScoreBreakdown` | 8 | Score bars |
| `LLMAnalysis` | 4 | AI verdict panel |
| `AssignmentResponse` | 12 | Assignment tracking |
| `DashboardStats` | 8 | StatsCard grid |
| `HeatmapPoint` | 7 | HeatMap |
| `DesertZone` | 6 | NeedDesertOverlay |
| `ActivityItem` | 7 | Activity feed (unused in UI) |
| `VolunteerLocation` | 6 | Map overlay |
| `ImpactResponse` | 8 | Volunteer impact (unused in UI) |

### 5.3 API Functions (18 functions)

| Function | Method | Endpoint |
|----------|--------|----------|
| `fetchNeeds` | GET | `/api/needs` |
| `fetchNeed` | GET | `/api/needs/:id` |
| `createNeed` | POST | `/api/needs` |
| `updateNeedStatus` | PATCH | `/api/needs/:id/status` |
| `fetchNeedStats` | GET | `/api/needs/stats/summary` |
| `fetchNeedMatches` | GET | `/api/needs/:id/matches` |
| `fetchMatchExplanation` | GET | `/api/needs/:id/matches/:vid/explain` |
| `fetchVolunteers` | GET | `/api/volunteers` |
| `fetchVolunteer` | GET | `/api/volunteers/:id` |
| `registerVolunteer` | POST | `/api/volunteers/register` |
| `fetchVolunteerImpact` | GET | `/api/volunteers/:id/impact` |
| `createAssignment` | POST | `/api/assignments` |
| `fetchAssignments` | GET | `/api/assignments` |
| `updateAssignmentStatus` | PATCH | `/api/assignments/:id/status` |
| `fetchDashboardStats` | GET | `/api/dashboard/stats` |
| `fetchHeatmap` | GET | `/api/dashboard/heatmap` |
| `fetchActivity` | GET | `/api/dashboard/activity` |
| `fetchDeserts` | GET | `/api/dashboard/deserts` |
| `fetchVolunteerLocations` | GET | `/api/dashboard/volunteer-locations` |
| `fetchHealth` | GET | `/health` |
| `fetchRegionalBriefing` | POST | `/api/system/regional-briefing` |
| `createChatWebSocket` | WS | `/ws/chat` |

### 5.4 Bugs in API Client

| Bug | Location | Severity |
|-----|----------|----------|
| `updateAssignmentStatus` sends `status`, `rating`, `feedback` as **query params** but backend expects a JSON body | Line 334 | 🔴 Will cause 422 |
| No `Authorization: Bearer <token>` header — all mutating requests fail when Firebase auth is enabled | `apiFetch()` | 🔴 Blocks production |
| `_explainCache` (client LLM cache) has no TTL or max size — grows unbounded | Line 270 | ⚠️ Memory leak in long sessions |
| `fetchVolunteers` return type is `VolunteerResponse[]` but backend returns `{volunteers, total}` paginated wrapper (based on backend route patterns) | Line 289 | ⚠️ May mismatch |

---

## 6. Utility Libraries

### 6.1 `lib/utils.ts` (62 lines) — 6 Functions

| Function | Purpose | Example |
|----------|---------|---------|
| `formatNeedType(type)` | Enum → label | `"WATER_SANITATION"` → `"Water & Sanitation"` |
| `formatPercent(value)` | 0–1 → percentage | `0.73` → `"73%"` |
| `initialsFromName(name)` | Name → avatar letters | `"Amit Sharma"` → `"AS"` |
| `urgencyLabel(urgency)` | Float → tier name | `0.95` → `"Critical"` |
| `urgencyColor(urgency)` | Float → hex color | `0.95` → `"#DC2626"` |
| `timeAgo(iso)` | ISO date → relative | `"2026-04-27T10:00:00"` → `"3h ago"` |

### 6.2 `lib/animations.ts` (31 lines) — 4 Presets

| Export | Used By | Effect |
|--------|---------|--------|
| `pageTransition` | All pages | Fade-in + slide-up (0.35s) |
| `cardVariants` | Needs/Volunteers grids | Staggered entry (40ms/card) |
| `barFill(value, delay)` | MatchCard score bars | Left-to-right fill animation |
| `buttonTap` | Submit buttons | Scale to 97% on press |

---

## 7. Configuration Files

### 7.1 `package.json`

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint"
  }
}
```

⚠️ `npm run dev` fails on this machine because `next` isn't in PATH. Workaround: `node node_modules/next/dist/bin/next dev`

### 7.2 `tsconfig.json`

- Target: ES2017
- Module: ESNext (bundler resolution)
- Strict mode: ✅ enabled
- Path alias: `@/*` → `./*` (was `./src/*`, fixed during review)
- JSX: react-jsx
- Plugins: `next`

### 7.3 `next.config.ts`

Empty — no custom webpack, redirects, rewrites, or image domains configured.

---

## 8. Dead Code — `src/app/` Directory

| File | Content | Status |
|------|---------|--------|
| `src/app/layout.tsx` | Default Next.js boilerplate with Geist fonts | 🔴 **Dead** — `app/layout.tsx` takes precedence |
| `src/app/page.tsx` | "Deploy Now" Vercel template | 🔴 **Dead** — `app/page.tsx` takes precedence |
| `src/app/globals.css` | Tailwind `@import` + dark mode vars | 🔴 **Dead** — not imported by `app/layout.tsx` |

**Recommendation:** Delete `src/app/` entirely — it's leftover from `create-next-app` scaffolding and causes confusion.

---

## 9. Missing Pages / Features

| Route | Referenced By | Exists? |
|-------|--------------|---------|
| `/needs/[id]` | `NeedCard` links to it, `needs/new` redirects to it | ❌ **Missing** — will 404 |
| `/volunteers/register` | "Register New" button on volunteers page, "Join as Volunteer" on landing | ❌ **Missing** — will 404 |
| `/volunteers/[id]` | Not linked but expected for profile view | ❌ **Missing** |
| `/needs/[id]/matches` | Would display MatchCard components | ❌ **Missing** |

---

## 10. Design System Analysis

### Color Palette

| Token | Hex | Usage |
|-------|-----|-------|
| Primary | `#059669` | Buttons, accents, brand (Emerald Green) |
| Primary Hover | `#047857` | Button hover state |
| Text Primary | `#1C1917` | Headings, body |
| Text Secondary | `#78716C` | Descriptions, labels |
| Text Tertiary | `#A8A29E` | Timestamps, muted |
| Border | `none` | Cards now use floating drop-shadows |
| Surface | `#F8FAFC` | Cool slate backgrounds |
| Neutral Surface | `#F5F5F4` | Bars, chips |
| Success | `#16A34A` / `#4D7C0F` | Available, valid match |
| Warning | `#CA8A04` / `#B45309` | Moderate urgency, weak match |
| Danger | `#DC2626` | Critical urgency, poor match |
| Info | `#2563EB` | Volunteer markers |

### Typography

| Element | Font | Weight | Size |
|---------|------|--------|------|
| Headings | Outfit | 400–700 | 18–52px |
| Body | Inter | 400–500 | 13–18px |
| Labels | Inter | 400 | 11–12px, uppercase, tracked |
| Stats | Outfit | 700 | 32–40px |

### Spacing & Radius

- Card padding: `20–24px`
- Card radius: `12px`
- Button radius: `8px`
- Pill radius: `9999px`
- Page max-width: `1280px`
- Content gap: `16px` (grid), `24px` (sections)

---

## 11. Line Count Summary

| Category | File | Lines |
|----------|------|-------|
| **Layout** | `app/layout.tsx` | 74 |
| **Pages** | `app/page.tsx` | 211 |
| | `app/dashboard/page.tsx` | 207 |
| | `app/needs/page.tsx` | 175 |
| | `app/needs/new/page.tsx` | 259 |
| | `app/volunteers/page.tsx` | 141 |
| **Components** | `MatchCard.tsx` | 325 |
| | `ChatPanel.tsx` | 143 |
| | `NeedCard.tsx` | 99 |
| | `HeatMap.tsx` | 87 |
| | `VolunteerCard.tsx` | 80 |
| | `NeedDesertOverlay.tsx` | 53 |
| | `StatsCard.tsx` | 37 |
| | `EmptyState.tsx` | 37 |
| | `LoadingBar.tsx` | 25 |
| **Libraries** | `lib/api.ts` | 382 |
| | `lib/utils.ts` | 62 |
| | `lib/animations.ts` | 31 |
| **Config** | `tsconfig.json` + `next.config.ts` + `package.json` | 76 |
| **Dead Code** | `src/app/*` | 127 |
| | | |
| **Active Total** | | **2,453** |
| **Dead Total** | | **127** |

---

## 12. All Issues — Priority Ranked

| # | Severity | Issue | File | Fix |
|---|----------|-------|------|-----|
| 1 | 🔴 Critical | No auth token in API client — all POST/PATCH/DELETE will 401 in production | `lib/api.ts` | Add Firebase token to `apiFetch` headers |
| 2 | 🔴 Critical | `updateAssignmentStatus` sends data as query params instead of JSON body | `lib/api.ts:334` | Change to `body: JSON.stringify({status, rating, feedback})` |
| 3 | 🔴 Critical | `/needs/[id]` page missing — NeedCard links and form redirects 404 | `app/needs/` | Create `app/needs/[id]/page.tsx` |
| 4 | 🔴 Critical | `/volunteers/register` page missing — CTA buttons 404 | `app/volunteers/` | Create `app/volunteers/register/page.tsx` |
| 5 | ⚠️ High | Navbar uses `<a>` tags — full page reloads on every navigation | `app/layout.tsx` | Switch to `next/link` `<Link>` |
| 6 | ⚠️ High | Google Fonts via `<link>` instead of `next/font` — no optimization | `app/layout.tsx` | Use `next/font/google` |
| 7 | ⚠️ High | Dashboard has no auto-refresh — stale after initial load | `dashboard/page.tsx` | Add SWR or polling interval |
| 8 | ⚠️ High | LLM explanation cache never expires or clears | `lib/api.ts:270` | Add TTL or LRU cap |
| 9 | ⚠️ Medium | Dead `src/app/` directory confuses project structure | `src/app/*` | Delete entirely |
| 10 | ⚠️ Medium | No mobile responsive navbar | `app/layout.tsx` | Add hamburger menu |
| 11 | ⚠️ Medium | ChatPanel loses messages on close/reopen | `ChatPanel.tsx` | Lift state up or persist |
| 12 | ⚠️ Medium | HeatMap has no India boundary outline | `HeatMap.tsx` | Add SVG path or GeoJSON |
| 13 | ⚠️ Low | SWR, Recharts, Lucide, clsx installed but unused | `package.json` | Remove or start using |
| 14 | ⚠️ Low | Button styles defined in `<style>` tags per-page instead of shared | Multiple pages | Extract to CSS module or shared component |
| 15 | ⚠️ Low | No error boundary — unhandled errors crash the whole page | App-wide | Add React Error Boundary |

---

*End of Frontend Report*
