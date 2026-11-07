# Build Log — Weather-Aware Truck Routing

Budget: 16 working hours / 4 calendar days (assessment cap). Build executed
2026-11-07 (PKT) in one autonomous session.

## Phase 1 — Requirements & planning ✅
- Read the full brief + the pre-verified provider facts (Nominatim / OSRM /
  Open-Meteo, all keyless; OSRM known to return only 2 alternatives on
  Chicago→St Louis → detour-waypoint fallback designed in).
- Wrote `docs/REQUIREMENTS_CHECKLIST.md` mapping every requirement to an
  implementation file and a test before writing application code.
- Provider decisions: Nominatim (geocoding), OSRM demo server (routing,
  alternatives=3 + documented detour fallback), Open-Meteo (weather, batched).
  All keyless — no API keys required from the candidate.
- Environment: Python 3.12.3, Node 24.22.1, npm 10.9.4. Django 5.1.15,
  DRF 3.15.2 installed into project-root `.venv`.

## Phase 2 — Foundation ✅
- Backend skeleton: `backend/config` + `backend/apps/{routing,weather,risk,recommendations}`
  + `backend/common/http.py` (shared provider HTTP: 10 s timeout, 1 retry).
- Frontend: Vite + React (JavaScript) scaffold, Leaflet via the plain
  `leaflet` package (imperative, with cleanup).

## Phase 3 — Core backend ✅
- Providers: Nominatim geocoding (clear error on unresolvable places),
  OSRM routing (`alternatives=3` + detour-waypoint fallback with
  geometry/distance dedupe), Open-Meteo batched weather (mph / inch /
  cm→inch snow conversion).
- Geometry service: cumulative haversine, interpolation along the real
  polyline, checkpoint placement (0, interval, …, end), ETA by
  constant-average-speed.
- Risk engine (`apps/risk/services/risk.py`): exact brief thresholds,
  boundary rule documented, all three load overrides, missing weather →
  UNKNOWN. Risk miles: segment rule with unknown miles reported separately;
  totals reconcile to route distance.
- Recommendation engine: lexicographic (severe → high → avg risk →
  duration); no-travel routes ranked below clean routes, explicit unsafe
  reasons; all-no-travel case recommends the least unsafe with a warning.
- API: `GET /api/v1/health/`, `POST /api/v1/routes/analyze/`,
  `POST /api/v1/routes/heatmap/` — consistent error shape, server-side
  validation, 502 on provider failure. Routes analyzed concurrently.

## Phase 4 — Frontend ✅
- TripForm (validation mirror, duplicate-submit guard), RouteComparison +
  RouteCard (recommended highlight, reasons, unsafe flags, risk bars),
  RouteMap (imperative Leaflet: all routes, recommended boldest, selected
  route checkpoints with weather/ETA/risk popups, auto-fit, heatmap
  corridor overlay), HeatmapPanel (debounced 0–48 h slider → real backend
  endpoint, forecast time display, legend), loading/error/empty states
  with retry.

## Phase 5 — Testing ✅ (all outputs captured in the delivery report)
- Backend: `python manage.py test` → **46 tests OK** (thresholds +
  boundaries, load rules, UNKNOWN handling, unit conversion, interpolation,
  ETA, risk-miles reconciliation, recommendation priority + no-travel,
  invalid inputs, mocked provider failure, response structure). All
  external calls mocked — suite runs offline.
- `python manage.py check` → no issues.
- `python manage.py check --deploy` (DJANGO_DEBUG=false, generated secret,
  SSL redirect on) → **no issues** (initial middleware warnings fixed by
  adding SecurityMiddleware, CsrfViewMiddleware, XFrameOptionsMiddleware;
  DRF views remain CSRF-exempt by design).
- Frontend: `npm test` → **10 tests passed** (3 files); `npm run lint` →
  clean; `npm run build` → success (dist JS 308.79 kB / gzip 95.24 kB).

## Phase 6 — Delivery ✅
- README (all 15 sections), docs/LOOM_PLAN.md, render.yaml,
  frontend/vercel.json, .env.example files, .gitignore.
- **Live smoke test (real network, 2026-11-07):** backend `runserver`,
  `POST /api/v1/routes/analyze/` Chicago → St Louis, departure
  2026-11-08T08:00:00Z, load 35,000 lb, interval 25 → **HTTP 200 in 5.26 s,
  3 routes**. OSRM directly returned 2 alternatives; the detour fallback
  supplied the genuine third (warning surfaced in the response, as
  designed). Checkpoints: 13 / 14 / 14 per route; risk miles reconciled
  exactly with route distance; weather values real (e.g. wind 11.5 mph at
  mile 25, ETA 08:28). Recommendation: route 1 (all routes tied on severe/
  high/avg-risk on a calm day → shortest duration won, per the priority
  order). Live heatmap call at +24 h → forecast_time 2026-11-09T08:00:00Z,
  13 points with real values.
- Frontend dev server verified serving (HTTP 200 for `/`, `main.jsx`,
  `App.jsx`).
- Local git repo initialized and committed. No push performed
  (GitHub CLI unauthenticated; account azlan98-not push handled separately
  by the parent agent).

## Deviations / decisions
- Frontend in JavaScript (not TypeScript) to reduce build risk — permitted by
  the commissioning instructions.
- Heatmap endpoint accepts an optional `duration_minutes` (the selected
  route's provider duration) so travel-time-to-point uses the same
  constant-average-speed ETA method as the analysis; when omitted it falls
  back to a documented 55 mph highway-speed estimate. The frontend always
  sends it for the selected route.
- Snowfall: Open-Meteo returns snowfall in cm; converted to inches (÷ 2.54).
  Rain requested with `precipitation_unit=inch`; wind with
  `wind_speed_unit=mph`.

## Post-deployment fix — 2026-11-07 (Open-Meteo 429 from hosted backend)

- Symptom: the Render-hosted backend returned HTTP 500 on
  POST /api/v1/routes/analyze/ while the same call succeeded locally.
  Render logs showed `common.http.ProviderError` — Open-Meteo answered
  HTTP 429 (Too Many Requests) from the host's shared egress IP — and the
  error escaped the weather layer.
- Fixes:
  - `common/http.py`: HTTP 429 is now retryable like 5xx, with exponential
    backoff (1s/2s/4s) honouring `Retry-After`; default retries 3.
  - `analysis.py`: all routes' checkpoints are fetched in ONE batched
    Open-Meteo request per analysis (was one request per route, fired in
    parallel), cutting provider calls per analysis from 3 to 1.
  - `weather_service.py` / `open_meteo.py`: forecast window is sized to the
    trip (days from today to the latest checkpoint ETA + 1, clamped 1..16)
    instead of always requesting 16 days; if the provider still fails, all
    checkpoints degrade to UNKNOWN risk (reported as unknown miles, never
    as safe) instead of failing the whole request.
  - New regression tests in `apps/weather/tests/test_resilience.py`
    (51 backend tests, all passing). Local live re-check: Chicago ->
    St. Louis returned HTTP 200, 3 routes, risk miles reconcile, weather
    available for every checkpoint.

## Post-deployment fix 2 — 2026-11-07 (worker timeout during 429 retries)

- Symptom: with the first fix live, analyze ran past Gunicorn's default
  30s worker timeout: Open-Meteo took ~10s to return each 429 from the
  hosted egress IP, and the retry backoff was still sleeping when the
  worker was killed (WORKER TIMEOUT in Render logs) — the graceful
  UNKNOWN degradation never got to respond.
- Fixes: provider budgets are now explicit and bounded — Open-Meteo
  timeout 8s / 1 retry, OSRM 8s / 1, Nominatim 6s / 1; shared client
  default is 1 retry with 0.5s/1s/2s backoff and Retry-After capped at
  3s. Worst-case weather budget is ~17s, inside the worker limit.
  Gunicorn start command gains `--timeout 120` as a safety margin
  (render.yaml + the live service's start command).
- 51 backend tests still passing.

## Post-deployment fix 3 — 2026-11-07 (backup weather provider)

- Symptom: with fixes 1–2 live, the hosted analyze endpoint returned 200
  with 3 routes, but EVERY checkpoint's weather was UNKNOWN — Open-Meteo
  kept answering HTTP 429 from Render's shared egress IP, so the graceful
  degradation was doing its job while the hosted demo showed no live
  weather or risk at all.
- Fix: a backup weather provider, MET Norway Locationforecast
  (`apps/weather/providers/met_norway.py`, keyless, identifies by
  User-Agent instead of per-IP quotas). `fetch_weather_for_points` now
  tries Open-Meteo first and falls back to MET Norway on ProviderError;
  only if both fail do checkpoints degrade to UNKNOWN (unchanged
  semantics). One call per point (max 8 parallel, 6s timeout, no
  retries), so the worst case stays inside the worker budget.
- Normalization: wind m/s -> mph; total precipitation mm/hr split into
  rain vs snow by the period's symbol_code (snow/sleet = snow at the
  10:1 water-to-depth ratio, otherwise rain) — documented approximation,
  fallback path only.
- Tests: 56 backend tests passing (5 new in
  `apps/weather/tests/test_met_norway.py`; the both-providers-down
  degradation test in `test_resilience.py` updated). Local live check
  with Open-Meteo forced unreachable: all sampled checkpoints returned
  real MET Norway weather (available=True).
