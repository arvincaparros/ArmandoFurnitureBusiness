# Full Frontend/Backend Integration + Authentication Audit

**Type:** Read-only audit. No source code, configuration, migrations, or API contracts were modified to produce this document.
**Repositories inspected:** `C:\Projects\ArmandoFurnitureBusiness\backend`, `C:\Projects\ArmandoFurnitureBusiness\frontend`
**Supporting docs read:** `frontend/FRONTEND_REQUIREMENTS.md`, `backend/docs/demand-forecasting-api-contract.md`, `backend/docs/demand-forecasting-frontend-backend-comparison.md` (**does not exist as a file on disk** — see conflict note below), `backend/docs/demand-forecasting-frontend-integration-plan.md`.

> **Documentation conflict found:** the audit prompt names `backend/docs/demand-forecasting-frontend-backend-comparison.md` as an existing document. It was not found in the repository (`Glob` for `**/demand-forecasting*` returns only `demand-forecasting-api-contract.md` and this session's own new files). The demand-forecasting comparison content this audit draws on instead comes from the prior conversation turn's live comparison work, not a file. Reported per the "report the conflict" instruction rather than silently substituted.

---

## 1. Executive Summary

**Authentication does not exist anywhere in this system.** Not partially, not as scaffolding with gaps — there is no user model, no password storage, no token issuance, no session mechanism, and no auth dependency wired into a single one of the 33 business endpoints across both repositories. The files that *look* like they should contain it — `backend/app/routers/auth.py`, `backend/app/schemas/auth.py`, `backend/app/services/auth.py` — exist as filenames only; all three are **0 bytes**. The frontend mirrors this exactly: `LoginPage.tsx` renders a bare `<h1>Login</h1>`, the "Logout" menu item has no click handler, and no auth context, store, hook, or token-storage code exists anywhere in `src/`.

Every one of the backend's 33 registered endpoints (across 11 routers) is reachable with zero credentials today — confirmed by reading every router file and finding `Depends(get_db)` as the only dependency used anywhere. There is also no CORS middleware configured on the FastAPI app, which is a separate, immediate blocker to *any* frontend-backend communication (not just authenticated communication) that will surface the moment the frontend's currently-mock-only pages are wired to real HTTP calls.

The frontend's own API integration is at 0% independent of auth: no shared HTTP client exists (`axios` is an installed-but-unimported dependency), no `.env`/`.env.example` exists, and `@tanstack/react-query` is provider-mounted but has zero `useQuery`/`useMutation` calls anywhere in the codebase. This means authentication work and general API-integration work are not sequential problems layered on a working system — they are the same greenfield problem, and should be scoped and estimated together rather than treating auth as an add-on to otherwise-working integrations.

**Bottom line:** nothing here can be completed "today" in the sense of shipping working authenticated integration — every phase requires net-new code on both sides. What *can* start immediately, with no blockers, is backend auth design and the frontend API-client/env scaffolding, both of which are additive and don't require decisions that are still open (see §16).

---

## 2. Backend Authentication Audit

### Method
Searched `backend/app` for auth-related keywords (login, logout, register, JWT, token, session, cookie, password, role, permission, `Depends(get_current`, `HTTPBearer`, `OAuth2PasswordBearer`, `CORSMiddleware`), read every router file's dependency list, read `app/database/models.py` in full for a `User`-shaped table, read `main.py`, checked `requirements.txt` for auth-related packages, checked all Alembic migrations for a users table, checked `backend/tests/` for auth test coverage.

### Findings

| Question | Answer |
|---|---|
| Does backend authentication exist? | **No.** |
| Is login implemented? | **NOT IMPLEMENTED.** `app/routers/auth.py`, `app/schemas/auth.py`, `app/services/auth.py` all exist as files but are confirmed 0 bytes — empty stubs, not partial implementations. |
| Exact login endpoint / method | **NOT IMPLEMENTED** — no route is defined in the empty `auth.py`, and `auth_router` is not imported or registered in `main.py`. |
| Request / response payload | **NOT IMPLEMENTED.** `app/schemas/auth.py` is empty — no `LoginRequest`/`LoginResponse`-style model exists to inspect. |
| Access token | **NOT IMPLEMENTED.** No token-issuing code anywhere. |
| Refresh token | **NOT IMPLEMENTED.** |
| Token type (JWT, opaque, session, etc.) | **UNKNOWN / NOT IMPLEMENTED** — cannot be verified because nothing issues a token. No JWT library (`python-jose`, `PyJWT`, `authlib`) or session library (`itsdangerous`) appears in `requirements.txt`. Do not assume JWT is intended; the dependency list gives no signal either way. |
| Token expiration | **NOT IMPLEMENTED.** |
| Where is the user stored? | **NOT IMPLEMENTED.** `app/database/models.py` defines exactly 11 tables (`Product`, `Resource`, `ProductResourceRequirement`, `ProductionCycle`, `CycleResource`, `ProductionAllocation`, `OptimizationRun`, `OptimizationResult`, `SalesTransaction`, `ForecastRun`, `ForecastResult`) — no `User`, `Account`, `Role`, or `Permission` table exists. Confirmed no Alembic migration (7 total, all reviewed) ever created or dropped a users table — this was never built, not removed. |
| How is the current user identified? | **NOT IMPLEMENTED** — no `get_current_user`-style dependency exists anywhere in the codebase. |
| Are roles implemented? | **No.** No `role` column, table, or enum anywhere. |
| Are permissions implemented? | **No.** |
| Are business endpoints protected? | **No — zero of them.** Verified by reading every `@router.get/post/patch/delete` decorator's parameter list across all 11 active routers (33 endpoints total, enumerated in §7): every single one takes only `db: Session = Depends(get_db)`. No endpoint anywhere takes an auth dependency. |
| Which endpoints are public? | **All 33.** See §7 for the full list. |
| Which require authentication? | **None, currently.** |
| Which require roles/permissions? | **None, currently.** |
| How are invalid credentials handled? | **NOT IMPLEMENTED** — no credential-checking code exists to have error handling. |
| How are expired tokens handled? | **NOT IMPLEMENTED.** |
| How are unauthorized requests handled? | **NOT IMPLEMENTED** — no request is ever rejected for lacking credentials; FastAPI's default 401/403 behavior is never triggered because no route declares a security dependency. |

### Additional findings surfaced during this audit (not on the original checklist, but relevant)

- **Two other routers are also empty stubs and unregistered**: `app/routers/forecasting.py` (0 bytes — note this is a *different* file from the actively-used `app/routers/forecast.py`) and `app/routers/reports.py` (0 bytes). Neither is imported in `main.py`. These appear to be earlier-stage scaffolding, unrelated to auth, but worth knowing they exist so they aren't mistaken for in-progress work.
- **No CORS middleware is configured anywhere.** `main.py` does not import or add `starlette.middleware.cors.CORSMiddleware`, and no other file in the backend adds middleware of any kind. This blocks *unauthenticated* frontend↔backend calls too, not just authenticated ones — see §9.
- **`requirements.txt` contains no authentication-capable package**: no `passlib`, `bcrypt` (standalone), `python-jose`, `PyJWT`, `authlib`, `fastapi-users`, or `itsdangerous`. The only cryptography-adjacent package (`cryptography==50.0.0`) is a transitive dependency of `google-auth`, not something the app code uses directly for password hashing or token signing (confirmed no import of it in `app/`).
- **`google-genai` is a direct dependency and `.env` contains a placeholder `GEMINI_API_KEY`**, but no file in `app/` imports or references `genai`/`Gemini` anywhere. This is circumstantial evidence that an AI/chat feature (matching the frontend's built-but-inert `ForecastChatbot.tsx`, previously flagged as "needs decision" in the forecasting integration plan) was anticipated but never started — noted here for context only; it is unrelated to authentication.
- **No `backend/tests/test_auth.py` or equivalent exists.** The 11 test files present cover dashboard, optimization, transactions, resources, products, resource utilization, and forecasting only.

---

## 3. Frontend Authentication Audit

### Method
Searched `frontend/src` for auth-related keywords (`localStorage`, `sessionStorage`, `document.cookie`, `useAuth`, `AuthContext`, `AuthProvider`, `authStore`, `isAuthenticated`, `axios.create`, `interceptors`, `401`, `403`, `Authorization`, `Bearer`), read `src/app/router.tsx`, `src/pages/auth/LoginPage.tsx`, `src/layouts/header/Header.tsx`, `src/layouts/header/UserMenu.tsx`, `src/layouts/AppLayout.tsx`.

### Findings

| Question | Answer |
|---|---|
| Is login currently implemented? | **No.** `LoginPage.tsx` is a two-line component: `const LoginPage = () => { return <h1>Login</h1> }`. No form, no fields, no submit handler, no validation. |
| Is logout implemented? | **No.** `Header.tsx` renders a "Logout" `Menu.Item` with `color="red"` and a `LogOut` icon but **no `onClick` handler at all.** Clicking it does nothing. |
| Is authentication state implemented? | **No.** No `AuthContext`, no auth store, no `useAuth` hook exists anywhere in `src/`. |
| Is current-user state implemented? | **No.** `Header.tsx`'s avatar hardcodes the literal letter `"A"` — there is no user object, name, or identity data flowing through the app anywhere. |
| Is token storage implemented? | **No.** The only `localStorage` usage in the entire frontend is `ThemeContext.tsx` persisting the light/dark theme preference (`localStorage.getItem('theme')` / `.setItem('theme', mode)`). No token, session id, or credential of any kind is read from or written to `localStorage`, `sessionStorage`, or `document.cookie` anywhere. |
| Are routes protected? | **No.** `router.tsx` defines `/login` as a standalone route and every other route (`/dashboard`, `/resources`, `/products`, `/production`, `/reports`, `/history`, `/optimization-history`, `/demand-forecasting`) nested under `<AppLayout>`, which renders `<Outlet/>` unconditionally in `AppLayout.tsx` — there is no guard component, no redirect-if-unauthenticated logic, and nothing prevents navigating directly to any business route without ever visiting `/login`. |
| Is there already an API client? | **No.** No `axios.create(...)` call exists anywhere in `src/`. `axios` is listed in `package.json` dependencies but is not imported by any file. |
| Is there already an interceptor? | **No.** No `.interceptors.request.use(...)` or `.interceptors.response.use(...)` exists anywhere — there is no client to attach one to. |
| How are API errors handled? | **N/A — no API calls exist to error.** Every page's hook (`useForecast`, `useDashboard` — itself an empty stub, `useProducts`, etc.) returns statically-imported mock arrays; none perform a network request, so there is no error path to observe. |
| What's missing, overall? | Everything: login UI/logic, logout logic, auth state/context, token storage, route guards, an HTTP client, request/response interceptors, and 401/403 handling. This is a complete, not partial, gap. |

### Additional finding
`src/layouts/header/UserMenu.tsx` exists as a file (separate from the account menu actually rendered inline inside `Header.tsx`) but is **0 bytes** — an unused stub, consistent with the pattern of scaffolded-but-empty components already noted in the frontend requirements audit (`Loading.tsx`, `ErrorView.tsx`, etc.).

---

## 4. API Client Audit

| Question | Answer |
|---|---|
| Is there a shared API client? | **No.** |
| Is axios configured? | **No** — installed, unused. |
| Is fetch wrapped? | **No** — no raw `fetch()` calls exist in `src/` either; the app currently performs zero network I/O to its own backend. |
| Is React Query configured? | **Partially — infrastructure only.** `QueryClient` is instantiated in `src/app/providers.tsx` with sensible defaults (`retry: 1`, `refetchOnWindowFocus: false`, `staleTime: 5min`) and `QueryClientProvider` wraps the whole app. But **zero `useQuery` or `useMutation` calls exist anywhere** — this is ready-to-use plumbing, not an active integration. |
| Where should authentication be integrated? | Into the shared API client that doesn't exist yet (§8) — specifically as a request interceptor attaching an `Authorization` header, and a response interceptor catching 401s to trigger logout/redirect. This must be built as part of Phase 2, not bolted onto individual page hooks. |
| Is there duplicated API logic? | Not currently, because there is no API logic at all yet to duplicate — every page independently imports its own `mock/*.ts` file through its own `use<Feature>.ts` hook. This is worth flagging as a *design* consideration for Phase 2: without a shared client, the same duplication pattern will likely reappear as raw `axios` calls scattered per-hook unless a shared client is established first. |
| Are API calls currently using mock data? | **Yes, universally.** Confirmed across all 8 functional business modules in `FRONTEND_REQUIREMENTS.md` — every hook returns static imports from a local `mock/*.ts` file with no exceptions. |

**Recommendation (reporting only, not implementing):** the least-disruptive place for an API client is a new `src/api/client.ts` wrapping the existing `axios` dependency (no new package needed), consumed by page hooks via `@tanstack/react-query`'s already-mounted `QueryClientProvider` (no new package needed there either). This reuses 100% of currently-installed-but-unused dependencies.

---

## 5. Authentication Contract

Per instruction, every field below that cannot be verified from actual code is marked `NOT IMPLEMENTED` rather than inferred or invented.

### Login
```
Method:    NOT IMPLEMENTED
Endpoint:  NOT IMPLEMENTED
Request:   NOT IMPLEMENTED
Response:  NOT IMPLEMENTED
Errors:    NOT IMPLEMENTED
```

### Logout
```
Method:    NOT IMPLEMENTED
Endpoint:  NOT IMPLEMENTED
Request:   NOT IMPLEMENTED
Response:  NOT IMPLEMENTED
Errors:    NOT IMPLEMENTED
```

### Current User
```
Method:    NOT IMPLEMENTED
Endpoint:  NOT IMPLEMENTED
Request:   NOT IMPLEMENTED
Response:  NOT IMPLEMENTED
Errors:    NOT IMPLEMENTED
```

### Token
```
Token type:               NOT IMPLEMENTED (do not assume JWT — no evidence either way in requirements.txt or code)
Token field:               NOT IMPLEMENTED
Expiration:                 NOT IMPLEMENTED
Refresh mechanism:          NOT IMPLEMENTED
Storage expectation:        NOT IMPLEMENTED
Authorization header format: NOT IMPLEMENTED
```

There is no partial contract to document. This section exists in the finished system's docs as a placeholder for work that has not started.

---

## 6. Frontend/Backend Authentication Compatibility

| Area | Frontend | Backend | Status | Required Work |
|---|---|---|---|---|
| Login | Stub page, no form/logic | Not implemented | 🔴 MISSING | Both sides built from scratch: backend login endpoint + credential verification; frontend login form + submit handler. |
| Logout | Menu item present, no handler | Not implemented | 🔴 MISSING | Backend needs a logout/invalidation mechanism appropriate to whatever token type is chosen (§16); frontend needs to wire the existing menu item. |
| Token issuance | No token handling code | Not implemented | 🔴 MISSING | Backend must decide and implement a token strategy before frontend work can target it. |
| Token storage | No token storage code (only theme in localStorage) | N/A — no token to store | 🔴 MISSING | Frontend storage mechanism depends on backend's token type decision (§16) — e.g. httpOnly cookie vs. localStorage changes the frontend approach entirely. |
| Authorization header | Not sent anywhere (no HTTP client exists) | Not read anywhere (no endpoint checks it) | 🔴 MISSING | Depends on token strategy decision. |
| Current user | No user state exists | No endpoint exists | 🔴 MISSING | Both sides net-new. |
| Protected routes | No route guard component exists | No endpoint requires auth | 🔴 MISSING | Frontend route guard is meaningless until backend actually rejects unauthenticated requests. |
| 401 handling | No interceptor exists (no client exists) | No route ever returns 401 (nothing to protect) | 🔴 MISSING | Must be built together — frontend interceptor has nothing to catch until backend endpoints start requiring auth. |
| 403 handling | Not implemented | Not implemented (no roles exist) | 🔴 MISSING | Blocked on roles/permissions decision (§16) — may be out of scope for a v1. |
| Token expiration | Not implemented | Not implemented | 🔴 MISSING | Depends on token type decision. |
| Refresh | Not implemented | Not implemented | 🔴 MISSING | Only relevant if a short-lived-token strategy is chosen; a session-cookie strategy may not need this at all — genuinely a design decision, not a gap to "fill in." |
| Roles | Not implemented, no UI reads a role | Not implemented, no role column exists | ⚪ NEEDS DECISION | Scope question: does this project need roles at all for v1, or is "authenticated vs. not" sufficient? Nothing in either repo signals an intended role model. |
| Permissions | Same as roles | Same as roles | ⚪ NEEDS DECISION | Same as above. |

Every row that isn't a scope question is 🔴 MISSING rather than 🟡 PARTIAL or 🟠 MISMATCH — there is no partial or conflicting implementation anywhere to reconcile; both sides are at zero.

---

## 7. Protected Endpoint Audit

All 33 endpoints below were confirmed by reading every router file's route decorators and dependency lists directly (not inferred from `main.py` alone). **Every single one is currently PUBLIC** — none currently requires authentication or authorization, because no such dependency exists in the codebase to apply.

| Module | Endpoint | Method | Auth Required (current) | Authorization (current) | Notes |
|---|---|---|---|---|---|
| Dashboard | `/api/dashboard/summary` | GET | None | None | |
| Resources | `/api/resources` | GET | None | None | |
| Resources | `/api/resources/{resource_id}` | GET | None | None | |
| Resources | `/api/resources` | POST | None | None | |
| Resources | `/api/resources/{resource_id}` | PATCH | None | None | |
| Resources | `/api/resources/{resource_id}` | DELETE | None | None | Soft-delete ("deactivate") per route summary. |
| Products | `/api/products` | GET | None | None | |
| Products | `/api/products/{product_id}` | GET | None | None | |
| Products | `/api/products` | POST | None | None | |
| Products | `/api/products/{product_id}` | PATCH | None | None | |
| Products | `/api/products/{product_id}` | DELETE | None | None | |
| Product Resource Requirements | `/api/products/{product_id}/resources` | GET | None | None | No dedicated frontend module — folded into Product Data Management per frontend audit. |
| Product Resource Requirements | `/api/products/{product_id}/resources` | POST | None | None | |
| Product Resource Requirements | `/api/products/{product_id}/resources/{resource_id}` | PATCH | None | None | |
| Product Resource Requirements | `/api/products/{product_id}/resources/{resource_id}` | DELETE | None | None | |
| Production Cycles | `/api/production-cycles` | GET | None | None | No frontend module, route, or type exists for "Production Cycles" as its own concept (frontend audit confirms). |
| Production Cycles | `/api/production-cycles` | POST | None | None | |
| Production Cycles | `/api/production-cycles/{cycle_id}` | GET | None | None | |
| Production Cycles | `/api/production-cycles/{cycle_id}` | PATCH | None | None | |
| Production Cycles | `/api/production-cycles/{cycle_id}` | DELETE | None | None | |
| Production Cycles | `/api/production-cycles/{cycle_id}/optimize` | POST | None | None | Likely backs the frontend's "Generate Optimal Production Plan" action once wired. |
| Production Cycles | `/api/production-cycles/{cycle_id}/optimize/apply` | POST | None | None | |
| Production Cycles | `/api/production-cycles/{cycle_id}/resource-consumption` | GET | None | None | |
| Production Cycles | `/api/production-cycles/{cycle_id}/feasibility` | GET | None | None | |
| Production Allocation | `/api/production-cycles/{cycle_id}/allocations` | GET | None | None | |
| Production Allocation | `/api/production-cycles/{cycle_id}/allocations` | POST | None | None | |
| Production Allocation | `/api/production-cycles/{cycle_id}/allocations/{product_id}` | PATCH | None | None | |
| Production Allocation | `/api/production-cycles/{cycle_id}/allocations/{product_id}` | DELETE | None | None | |
| Resource Utilization | `/api/resource-utilization` | GET | None | None | |
| Resource Utilization | `/api/resource-utilization/{cycle_id}` | GET | None | None | |
| Transaction History | `/api/transactions` | GET | None | None | |
| Transaction History | `/api/transactions/{transaction_id}` | GET | None | None | |
| Transaction History | `/api/transactions` | POST | None | None | |
| Transaction History | `/api/transactions/{transaction_id}` | PATCH | None | None | |
| Transaction History | `/api/transactions/{transaction_id}` | DELETE | None | None | |
| Optimization History | `/api/optimization/history` | GET | None | None | This is the only backend surface under an "optimization" prefix — there is no separate live "run an optimization" endpoint here (that's under Production Cycles' `/optimize`), matching the frontend audit's note that a standalone "Optimization" module (distinct from Production Allocation and Optimization History) doesn't exist on the frontend either. |
| Optimization History | `/api/optimization/history/{run_id}` | GET | None | None | |
| Demand Forecasting | `/api/forecast` | GET | None | None | |
| Demand Forecasting | `/api/forecast/generate` | POST | None | None | |
| Demand Forecasting | `/api/forecast/timeseries` | GET | None | None | |
| Forecast History | `/api/forecast/history` | GET | None | None | |
| Forecast History | `/api/forecast/history/latest` | GET | None | None | |
| Forecast History | `/api/forecast/history/{run_id}` | GET | None | None | |

**ROLE-RESTRICTED column omitted from the table above** because zero endpoints have any authorization logic to report — adding an always-"None" column would only repeat the previous column. No endpoint in either repository currently distinguishes between user roles in any way.

---

## 8. Module Integration Readiness

| Module | Frontend Exists | Backend API Exists | Auth Required (today) | API Client Ready | Integration Ready | Main Blocker |
|---|---|---|---|---|---|---|
| Dashboard | ✅ `/dashboard` | ✅ `/api/dashboard/summary` | No | ❌ | ❌ | No shared API client exists yet (§4); page is 100% mock. |
| Resources Management | ✅ `/resources`, full CRUD UI | ✅ full CRUD | No | ❌ | ❌ | Same — no API client. |
| Product Data Management | ✅ `/products`, create/search/sort working; edit/delete built but unreachable in UI | ✅ full CRUD, plus a separate Product Resources sub-router the frontend doesn't call independently | No | ❌ | ❌ | No API client; frontend's own edit/delete wiring gap (pre-existing, unrelated to auth) would also need fixing to reach full CRUD parity. |
| Production Cycles | ❌ No module exists at all | ✅ full CRUD + optimize/apply/feasibility endpoints | No | ❌ | ❌ | Frontend has nothing to integrate — this is a net-new frontend module, not a wiring task. |
| Production Allocation | ✅ `/production`, "Generate Plan" button is a no-op | ✅ optimize/apply endpoints + allocations CRUD | No | ❌ | ❌ | No API client; also no input form exists yet for whatever parameters `/optimize` expects (frontend audit: "whatever request shape backs 'generate' is not yet expressed anywhere in the frontend code"). |
| Resource Utilization Report | ✅ `/reports`, read-only | ✅ `/api/resource-utilization[/{cycle_id}]` | No | ❌ | ❌ | No API client. |
| Transaction History | ✅ `/history`, create/search/sort/export working; edit/delete hook exists but no UI | ✅ full CRUD | No | ❌ | ❌ | No API client. |
| Optimization | ❌ No standalone module (folded into Production Allocation + Optimization History per frontend audit) | Partially — only history endpoints live under `/api/optimization`; the "run" action lives under Production Cycles | No | ❌ | ❌ | Conceptual mismatch, not a technical one — "Optimization" isn't a single addressable module on either side. |
| Optimization History | ✅ `/optimization-history`, "Run Manual Optimization" is a no-op | ✅ `/api/optimization/history[/{run_id}]` | No | ❌ | ❌ | No API client. |
| Demand Forecasting | ✅ `/demand-forecasting`, "Run Demand Optimization" is a no-op, chat UI is inert | ✅ `/api/forecast`, `/api/forecast/generate`, `/api/forecast/timeseries` | No | ❌ | ❌ | Already has a dedicated plan — see `demand-forecasting-frontend-integration-plan.md` and §13 Phase 6. |
| Forecast History | ❌ No module exists at all (frontend audit explicitly confirms) | ✅ `/api/forecast/history[/latest][/{run_id}]`, fully tested | No | ❌ | ❌ | Net-new frontend module, same category as Production Cycles. |

**Cross-cutting observation:** "Integration Ready" is ❌ for every single module, and for the same root cause in 9 of 11 rows — the absent shared API client (§4), not auth. Only Production Cycles and Forecast History have a *second*, independent blocker (no frontend module exists at all). This means the API-client work in Phase 2 (§13) unblocks the majority of modules at once, while Production Cycles and Forecast History additionally require net-new frontend build-out regardless of auth status.

---

## 9. Environment/CORS Configuration

### Frontend
| Item | Status |
|---|---|
| `.env` | **Does not exist.** |
| `.env.development` | **Does not exist.** |
| `.env.example` | **Does not exist.** |
| Vite config (`vite.config.ts`) | Minimal — only `@vitejs/plugin-react` is configured. No `server.proxy`, no `define`, no env handling of any kind. |
| API base URL | **Not configured anywhere** — there is nothing to configure since no HTTP client exists. |
| Dev server / proxy | **No proxy configured.** Running `npm run dev` (Vite, default port 5173) today has no path to reach the backend even for public, unauthenticated endpoints. |

### Backend
| Item | Status |
|---|---|
| CORS configuration | **Not configured.** `main.py` does not import or register `CORSMiddleware` (or any middleware). Confirmed by reading `main.py` in full and grepping the entire backend tree for "cors" — the only matches are in documentation, not code. |
| Environment variables | `backend/.env` exists and defines `DATABASE_URL` and a placeholder `GEMINI_API_KEY`. `backend/.env.example` exists but is **0 bytes** — no template for other developers to copy. |
| API prefix | Consistent `/api/...` prefix pattern across all 11 routers (see §7 for the full path list) — no global prefix is applied at the `FastAPI()` app level, each router sets its own. |
| Host/port | Not pinned in code — presumably run via `uvicorn main:app` with default/CLI-supplied host/port; no `Config`/`Settings` class exists to inspect for this. |
| Authentication configuration | **N/A — nothing to configure**, per §2. |

### Can the frontend currently communicate with the backend?

**No — not for any endpoint, authenticated or not.** Two independent blockers exist today, and both would need addressing regardless of auth:

1. **No CORS policy on the backend.** A browser-based fetch from `http://localhost:5173` (Vite dev default) to a backend running on a different origin/port will be blocked by the browser's same-origin policy unless the backend adds `CORSMiddleware` (or the frontend routes through a Vite dev proxy so the browser only ever talks to its own origin).
2. **No API base URL or client exists on the frontend** to attempt such a call in the first place (§4).

**Once auth is added, a third blocker becomes relevant:** if the eventual token strategy uses cookies, `CORSMiddleware` also needs `allow_credentials=True` and an explicit (non-wildcard) `allow_origins` list — a wildcard origin cannot be combined with credentialed requests per the CORS spec. This is a forward-looking note, not a current gap, since no token strategy has been chosen yet (§16).

---

## 10. Security Considerations

Since no authentication approach has been chosen or implemented, this section identifies risks to weigh **when** a design is chosen, rather than auditing an existing (nonexistent) implementation.

| Area | Consideration |
|---|---|
| Token storage | If a bearer-token strategy is chosen, `localStorage` is vulnerable to XSS-based token theft; an httpOnly cookie avoids that but introduces CSRF considerations instead and requires the CORS `allow_credentials` change noted in §9. This tradeoff should be made deliberately (§16), not defaulted into. |
| Password handling | Not applicable yet — no credential storage exists. When it does, a vetted hashing library (e.g. `passlib[bcrypt]`) should be added; none is currently in `requirements.txt`. |
| Token expiration | Undecided. Whatever is chosen, the frontend's 401-handling path (currently nonexistent, §3) needs to exist before any expiration policy is meaningful in practice — an expired token with no frontend handling just becomes a silent failure. |
| Refresh handling | Only relevant if short-lived tokens are chosen; not a given requirement (§6). |
| Logout behavior | The frontend already has a "Logout" menu item with no handler — whatever backend logout mechanism is chosen, at minimum the frontend needs to clear whatever it stored client-side, not just call an endpoint. |
| Unauthorized access | Today, this isn't a "risk" so much as the current, complete state: **every business endpoint is fully open**, including all write operations (POST/PATCH/DELETE on Resources, Products, Transactions, Production Cycles, Allocations). Anyone with network access to the backend can read and mutate all business data with no credentials. This is worth stating plainly rather than softened, since it's the actual current state, not a hypothetical. |
| Protected routes | The frontend has no route guard component today (§3) — this is a pure frontend UX gap (unauthenticated users can navigate to any page in the browser) that only matters once the backend actually starts rejecting unauthenticated API calls; right now a route guard alone would be cosmetic, since the underlying data would still load for anyone who bypassed it. |
| Accidental exposure of protected APIs | Not yet applicable — nothing is protected to accidentally expose. Worth re-checking this audit's §7 table again once auth is added, to confirm every endpoint that *should* require auth actually does (a common regression is forgetting the dependency on a newly-added endpoint). |

No redesign is proposed here, per instructions — these are considerations to carry into whatever design is chosen in Phase 1 (§13), not a critique of an existing approach.

---

## 11. Integration Dependencies

Based on the actual state of both repositories (not a generic template), the dependency order is:

```
1. Backend auth design decision (token type, roles y/n)   — blocks everything downstream; see §16
   ↓
2. Backend: user model + migration + login/logout/current-user endpoints
   ↓
3. Backend: CORS configuration                              — independent of (1)/(2), can happen in parallel;
   ↓                                                            blocks ALL frontend↔backend calls, auth or not
4. Frontend: shared API client (axios instance) + env config — independent of (1)/(2), can start immediately
   ↓
5. Frontend: auth state/context + token storage              — depends on (1)'s decision and (2) existing
   ↓
6. Frontend: login page + logout wiring                       — depends on (2) + (5)
   ↓
7. Frontend: route guards + 401/403 interceptor handling      — depends on (4) + (5) + backend endpoints actually enforcing auth (2)
   ↓
8. Backend: add auth dependency to business routers            — depends on (2); can be done incrementally per-router
   ↓
9. Frontend: wire each business module's hooks to real endpoints via the shared client — depends on (4), and on (8) for that specific module if it's protected
   ↓
10. Demand Forecasting integration                             — its own plan already exists (§13 Phase 6); depends on (4) at minimum, (8) if forecast endpoints become protected
   ↓
11. End-to-end validation across all modules                    — depends on everything above
```

**Key insight specific to this codebase:** steps 3 and 4 (CORS + frontend API client) have **no dependency on the auth decision at all** and can start today without blocking on anything in §16. Everything from step 5 onward is genuinely blocked on the auth design decision.

---

## 12. Full Integration Implementation Plan

Read-only plan. No code implied by this section has been written.

### Phase 1 — Authentication Foundation

**Backend work required:**
- Decide token strategy (§16 — blocks all backend work below).
- Add a `User` model + Alembic migration (none exists today).
- Add password hashing (a library must be added to `requirements.txt` — none exists today).
- Implement `app/services/auth.py` (currently empty) and `app/schemas/auth.py` (currently empty) — login/token-issuance logic and request/response schemas.
- Implement `app/routers/auth.py` (currently empty) — login endpoint, and logout/current-user endpoints per the chosen strategy.
- Register the new router in `main.py` (currently only 11 routers are registered; auth would be the 12th).
- Add a `get_current_user` dependency for use by protected routers.

**Frontend work required:**
- None yet at this phase beyond awaiting the contract — frontend auth UI depends on the backend contract existing first (§11).

**Files involved:** `backend/app/routers/auth.py`, `backend/app/schemas/auth.py`, `backend/app/services/auth.py`, `backend/app/database/models.py`, a new Alembic migration, `backend/main.py`, `backend/requirements.txt`.

**Expected result:** a working, testable login/logout/current-user contract with no business endpoints protected yet — this phase is purely about the auth endpoints existing and being correct in isolation.

### Phase 2 — Shared API Client

**Frontend work required:**
- Introduce `.env`/`.env.example`/`.env.development` with an API base URL variable (none exists today).
- Decide and implement the CORS-vs-proxy strategy from §9 (backend CORS config is a parallel/backend-side task here).
- Build a shared `axios` instance (already a dependency) with base URL from env.
- Add a request interceptor attaching the `Authorization` header (or ensure `withCredentials: true` if a cookie strategy was chosen in Phase 1) — exact shape depends on Phase 1's decision.
- Add a response interceptor handling 401 (redirect to `/login` + clear stored auth state) — 403 handling only if roles/permissions are in scope (§16).

**Files involved:** new `src/api/client.ts` (or similar — no such file exists today), new `.env*` files, `src/app/providers.tsx` (already has `QueryClient` — no new provider needed, just consumption).

**Expected result:** one reusable, authenticated HTTP client that every business module's hooks can be rewritten to use, with 401 handling centralized instead of per-page.

### Phase 3 — Login / Logout / Protected Routes

**Frontend work required:**
- Replace `LoginPage.tsx`'s stub with a real form calling Phase 1's login endpoint via Phase 2's client.
- Build auth state (context or a small store) holding the current-user/authenticated flag — none exists today.
- Wire `Header.tsx`'s existing, currently-inert "Logout" `Menu.Item` to actually call logout and clear state.
- Add a route-guard wrapper around the routes currently nested under `<AppLayout>` in `router.tsx` (today `<Outlet/>` renders unconditionally with no check).
- Add an "unauthorized" redirect path (e.g. back to `/login`) triggered by Phase 2's 401 interceptor.

**Backend work required:**
- None new — this phase consumes Phase 1's endpoints; business routers are still unprotected at this point per the dependency order in §11 (protecting them is Phase 4+, incrementally).

**Expected result:** a user can log in, see their session persist across a refresh, get redirected out on 401, and use a working logout — before any business module's data is real yet.

### Phase 4 — Core Modules

Dashboard, Resources, Products, Product Resources, Production Cycles, Production Allocation.

**Per-module work (repeats 6 times):**
- Backend: decide whether this module's endpoints require auth at all (§16 may resolve this globally, or per-module) and add the `get_current_user` dependency if so.
- Frontend: replace the module's `use<Feature>.ts` mock-returning hook with `useQuery`/`useMutation` calls through Phase 2's client.
- Production Cycles specifically also requires **building a new frontend module from scratch** (§8) — this is not a wiring task like the other five.
- Production Allocation additionally requires designing a request form for whatever parameters `/optimize` expects, since the frontend currently defines none (§8).

**Expected result:** these six modules render real backend data and real CRUD/action results instead of mock arrays, under whatever auth policy was decided.

### Phase 5 — Reporting Modules

Resource Utilization, Transaction History, Optimization, Optimization History.

**Per-module work:** same pattern as Phase 4 — replace mock-returning hooks with real queries. "Optimization" as a standalone concept doesn't exist on either side (§8) — no work item exists for it beyond what Optimization History and Production Allocation already cover.

**Expected result:** these four surfaces show real historical/reporting data.

### Phase 6 — Demand Forecasting

**Do not recreate the forecasting plan** — it already exists in full at `backend/docs/demand-forecasting-frontend-integration-plan.md` and should be followed as-is for the *what* of this module's integration (its 5-phase breakdown: live table → generate action → chart → new history module → deferred chat).

**How it fits into the authenticated application:**
- That plan's Phase 1 ("API client + Decimal parser + adapter scaffolding") should be treated as satisfied by *this* audit's Phase 2 (§13) rather than built separately — it's the same shared client, not a forecasting-specific one.
- If forecast endpoints become auth-protected as part of this audit's Phase 4/5 rollout, the forecasting plan's `useQuery`/`useMutation` calls automatically inherit auth headers/401 handling from the shared client — no forecasting-specific auth code should be needed.
- The forecasting plan's own §9 flagged CORS/proxy as a "decision needed" — that decision should be made once, here, in this audit's Phase 2, not re-decided independently for forecasting.
- The forecasting plan's new Forecast History module (its Phase 4) should reuse whatever route-guard pattern this audit's Phase 3 establishes, the same as any other new route added to `router.tsx`.

No other changes to the forecasting plan's content or sequencing are implied.

### Phase 7 — End-to-End Validation

- Login with valid credentials → lands on `/dashboard` with real data.
- Login with invalid credentials → backend's documented error response, surfaced clearly in the login form (not a raw stack trace).
- Every protected endpoint rejects a request with no/invalid token (401) and, if roles are in scope, rejects a wrong-role request (403).
- CRUD operations against Resources, Products, Transactions, Production Cycles, Allocations all round-trip correctly against the real backend.
- Route guards correctly redirect an unauthenticated direct navigation to any business route.
- Token expiration is handled gracefully mid-session (whatever that means for the chosen strategy — silent refresh, or forced re-login).
- Logout clears client-side state and backend session/token validity (per whatever mechanism Phase 1 chose) and returns the user to `/login`.
- All 11 business modules (§8) render real data, not mocks.
- Demand Forecasting's own module-specific verification steps, per its plan's §13 "Testing & Verification Plan."
- A full regression pass confirming no previously-mock-driven UI silently broke when its data source changed (e.g. null-safety for fields that were always present in mock data but can be null from the real API — the forecasting plan's §12 error-handling table is a good template for this per-module).

---

## 13. Today's Completion Assessment

### Can Be Completed Today
- Nothing that constitutes "working authenticated integration." What genuinely has zero blockers and could start immediately: the backend auth design decision itself (§16), scaffolding `backend/app/routers/auth.py` et al. with a chosen approach, and the frontend's `.env`/API-client scaffolding (Phase 2) — none of that depends on anything not already in the repos.

### Requires Backend Work
- User model + migration, password hashing, token issuance/validation, login/logout/current-user endpoints, CORS middleware, and — incrementally, per module — adding an auth dependency to the 33 currently-public endpoints in §7.

### Requires Frontend Work
- Shared API client, env configuration, auth state/context, token storage, real login form, logout wiring, route guards, 401/403 interceptor handling, and rewriting every page's mock-returning hook to call real endpoints (all 11 modules) — plus building two modules that don't exist on the frontend at all yet (Production Cycles, Forecast History).

### Potential Blockers
- **§16's open decisions are the critical-path blocker** — token type, roles-or-not, and CORS/proxy strategy all need an answer before backend Phase 1 can be implemented correctly the first time, rather than built and reworked.
- **No CORS config today blocks even unauthenticated integration** — this would surface as a confusing browser-console error the moment anyone tries the "quick win" of wiring one module to the backend without addressing it first.
- **`.env.example` being empty** (§9) means there's currently no committed template signaling to a new developer what backend env vars are even expected — a minor but real onboarding blocker once auth adds more required vars (e.g. a signing secret).

### Highest-Risk Items
1. **Choosing a token strategy without a stated requirement for it** (§16) — the risk isn't technical difficulty, it's that this project has given no signal (no library installed, no partial code, no design doc) about what's actually needed, so any choice made without stakeholder input risks being redone.
2. **Production Cycles and Forecast History requiring net-new frontend modules**, not just wiring — these will take materially longer than the other 9 modules and could be mis-estimated if treated the same as a "just add useQuery" task.
3. **The frontend's existing unreachable Edit/Delete UI** (Product Data Management, Transaction History — flagged in the frontend requirements audit, not this one) will surface as "broken" the moment real data replaces mocks, even though it's a pre-existing gap unrelated to auth.

### Dependencies
See §11 for the full ordered chain. The single hardest dependency to short-circuit is that steps 5–11 all trace back to §16's decisions being made first.

---

## 14. Final Status

| Area | Current Status | Remaining Work |
|---|---|---|
| Authentication | Not implemented (stub files only, 0 bytes) | Full backend build: user model, migration, password handling, token issuance, login/logout/current-user endpoints. |
| API client | Not implemented (dependencies installed, unused) | Build shared `axios` + React Query integration, env config, interceptors. |
| Protected routes | Not implemented on either side | Frontend route guard; backend per-endpoint auth dependency. |
| Dashboard | Mock data only | Wire to `GET /api/dashboard/summary` via shared client. |
| Resources | Mock data only, frontend CRUD UI fully built | Wire full CRUD to `/api/resources`. |
| Products | Mock data only, edit/delete UI built but unreachable | Wire CRUD; separately fix frontend's own unreachable edit/delete wiring. |
| Production (Cycles + Allocation) | No frontend module for Cycles; Allocation UI's "Generate Plan" is a no-op | Build Production Cycles module from scratch; wire Allocation's action + design its input form. |
| Resource Utilization | Mock data only | Wire to `/api/resource-utilization[/{cycle_id}]`. |
| Transactions | Mock data only, edit/delete hook exists, no UI | Wire CRUD; add edit/delete UI if desired. |
| Optimization | No standalone frontend concept; backend only exposes history | No dedicated work — covered by Production Allocation + Optimization History. |
| Optimization History | Mock data only, "Run" action is a no-op | Wire to `/api/optimization/history[/{run_id}]`. |
| Demand Forecasting | Mock data only, "Run" and chat are no-ops | Follow existing `demand-forecasting-frontend-integration-plan.md`, Phases 1–3. |
| Forecast History | No frontend module at all | Build from scratch per the forecasting plan's Phase 4. |
| End-to-end testing | No auth tests exist; no frontend test runner installed at all | Add auth test coverage on backend; decide on and add a frontend test runner (`vitest`/`jest` — neither exists today) if automated frontend testing is desired. |

---

## 15. Final Recommendation

1. **What is the FIRST thing we should implement?**
   Resolve §16's open decisions (token type, roles-in-scope-or-not, CORS/proxy approach), then implement the backend auth foundation (Phase 1: user model, migration, login/logout/current-user endpoints). Nothing downstream can be built correctly without this being settled first.

2. **What should be implemented immediately after?**
   The frontend shared API client + env config (Phase 2) — it can technically start in parallel with Phase 1 since it doesn't depend on auth specifics for its *scaffolding* (base URL, axios instance, React Query wiring), but the interceptor logic within it does depend on Phase 1's token-type decision, so treat Phase 2 as "start early, finish after Phase 1 lands."

3. **Which modules can be integrated without backend changes?**
   None, in the sense of "no backend work at all" — every module's backend endpoints already exist (§7/§8) and require no *new* backend work to wire up for reading/writing data, but all of them are currently blocked by the missing CORS config and missing frontend API client (§9/§4), which are backend-adjacent/frontend prerequisites, not module-specific backend work. Once Phase 2 lands, Dashboard, Resources, Products, Resource Utilization, Transaction History, and Optimization History can all be wired with zero additional backend endpoint work.

4. **Which modules are blocked?**
   Production Cycles and Forecast History are blocked on frontend module construction, not backend availability — both APIs already exist and are ready. Production Allocation is blocked on both a missing input-form design and its wiring. Demand Forecasting has its own detailed plan already and isn't "blocked" so much as sequenced (§13 Phase 6).

5. **What backend work is required?**
   The full auth foundation (§13 Phase 1), CORS middleware, and — once auth exists — incrementally adding the `get_current_user` dependency to whichever of the 33 endpoints in §7 are decided to need protection.

6. **What frontend work is required?**
   Shared API client, env config, auth state/context, token storage, real login form, logout wiring, route guards, 401 handling, and rewriting all 11 modules' hooks from mock data to real queries — plus building the two modules that don't exist yet.

7. **What could prevent completing full integration today?**
   Everything in §13's "Potential Blockers" — but the root cause underneath all of them is the same: **no authentication design decision has been made yet**, and a meaningful fraction of both the backend and frontend work described in this document cannot be started correctly without that decision existing first.

---

## START HERE

**The exact first implementation task after reviewing this audit is:** make the token-strategy and roles-in-scope decisions in §16 (a product/stakeholder conversation, not an engineering task), then begin backend Phase 1 (§13) by implementing `backend/app/services/auth.py` and `backend/app/schemas/auth.py` — both currently empty files — starting with the `User` model + Alembic migration those services will depend on, since no user table exists anywhere in the database today.

---

## 16. Open Decisions Requiring Product/Stakeholder Input

(Referenced throughout this document; consolidated here for visibility.)

| # | Decision | Why engineering can't resolve it alone |
|---|---|---|
| 1 | Token strategy — short-lived JWT + refresh token, long-lived session cookie, or something else | No library, partial code, or design doc in either repo signals an intended direction; this is a genuine architecture choice with real security/UX tradeoffs (§10), not something to infer from existing patterns. |
| 2 | Are roles/permissions in scope for v1, or is "authenticated vs. not" sufficient? | No role concept exists anywhere in the data model or UI today (§2/§3) — adding it is a scope decision, not a technical gap. |
| 3 | CORS-with-credentials vs. a Vite dev proxy for local development | Both solve §9's communication blocker; the choice affects the token-storage decision above (cookie-based auth needs the CORS+credentials path). |
| 4 | Which of the 33 endpoints in §7 actually need protection, vs. which (if any) should remain intentionally public | Not knowable from the code — e.g., should `GET /api/dashboard/summary` require login, or is some read-only data intentionally public? This is a business decision per module, not a default to assume "protect everything." |
| 5 | Whether the forecasting module's chat assistant (§2's `GEMINI_API_KEY` finding) is in scope at all | Flagged as "needs decision" in the existing forecasting integration plan already; repeated here only because it surfaced again during this audit's backend dependency review — not a new finding. |
