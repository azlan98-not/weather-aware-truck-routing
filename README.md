# Weather-Aware Truck Routing

A full-stack application built for the **Spotter AI Full Stack Developer
technical assessment**. Given an origin, destination, departure time and
truck load, it generates up to **three genuine route alternatives**, samples
**live weather forecasts at each checkpoint's estimated arrival time** along
each route, classifies weather risk with the assessment's exact thresholds
and load rules, and deterministically recommends the safest route.

![Stack](https://img.shields.io/badge/stack-React%20%2B%20Django%20REST-blue)

## 1. Project overview

Dispatchers planning a truck trip need to know not just which route is
fastest, but which route is safest for the weather the truck will actually
drive through. This app:

- Geocodes the origin/destination and fetches up to 3 real driving routes.
- Places weather checkpoints every 10, 25 or 50 miles along each route's
  actual geometry.
- Looks up the forecast for the hour the truck is estimated to **arrive**
  at each checkpoint (not the departure time).
- Classifies wind/rain/snow risk per checkpoint, applies load-based
  overrides, aggregates risk miles per route, and recommends a route by the
  brief's exact priority order.

## 2. Architecture overview

```
┌────────────┐   POST /api/v1/routes/analyze/    ┌──────────────────────────────┐
│  React     │ ────────────────────────────────▶ │ Django REST API              │
│  frontend  │   POST /api/v1/routes/heatmap/    │  views → serializers →       │
│  (Vite +   │ ◀──────────────────────────────── │  services → providers        │
│  Leaflet)  │        JSON (routes, risk,        └──────┬───────┬───────┬───────┘
└────────────┘        recommendation)                   │       │       │
                                                 Nominatim   OSRM   Open-Meteo
                                                 (geocode) (routing) (weather)
```

- **Providers** isolate every external API behind a small module, so any of
  them can be swapped without touching business logic.
- **Risk engine** (`apps/risk`) is a pure, centralized module — the only
  place thresholds live — and is independently unit-testable.
- **Recommendation engine** (`apps/recommendations`) is a pure
  lexicographic comparator over route summaries.
- Routes are analyzed concurrently; each route's weather is fetched in one
  batched Open-Meteo call.

## 3. Technology stack

| Layer | Technology |
|---|---|
| Frontend | React 18 (JavaScript), Vite 5, Leaflet 1.9 (imperative) |
| Backend | Python 3.12, Django 5.1, Django REST Framework 3.15 |
| Database | SQLite (local default); PostgreSQL via `DATABASE_URL` |
| Geocoding | OpenStreetMap Nominatim (keyless) |
| Routing | OSRM demo server (keyless), `alternatives=3` + detour fallback |
| Weather | Open-Meteo forecast API (keyless) |
| Tests | Django test runner (46 tests), Vitest + Testing Library (10 tests) |
| Hosting prep | Render (backend blueprint), Vercel (frontend static) |

## 4. Features

- Trip form with frontend + backend validation and duplicate-submit guard.
- Up to 3 genuine route alternatives (provider alternatives plus a genuine
  detour-waypoint fallback — never fabricated or duplicated).
- Checkpoints at 10/25/50-mile intervals interpolated along real geometry.
- Weather evaluated at each checkpoint's estimated arrival time.
- Exact wind/rain/snow risk thresholds and all three load-based rules.
- Per-route risk miles (low/moderate/high/severe/no-travel/**unknown**),
  distance-weighted average risk, highest risk, risky checkpoint count.
- Deterministic recommendation: fewest severe miles → fewest high miles →
  lowest average risk → shortest duration; no-travel routes flagged unsafe.
- Interactive map: all routes, risk-colored checkpoint markers with
  weather/ETA popups, card↔map selection sync, auto-fit bounds.
- Corridor weather heatmap with a real 0–48 h forecast slider backed by a
  dedicated API endpoint (no simulated data).
- Loading, error (with retry), empty and warning states throughout.

## 5. Project structure

```
weather-aware-truck-routing/
├── backend/
│   ├── config/                 # settings, urls, wsgi/asgi
│   ├── common/http.py          # shared provider HTTP (timeout + 1 retry)
│   ├── apps/
│   │   ├── routing/            # views, serializers, urls
│   │   │   ├── providers/      # nominatim.py, osrm.py
│   │   │   ├── services/       # analysis.py, geometry.py, heatmap.py
│   │   │   └── tests/
│   │   ├── weather/            # providers/open_meteo.py, services/
│   │   ├── risk/               # services/risk.py (centralized risk engine)
│   │   └── recommendations/    # services/recommender.py
│   ├── manage.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/                # client.js, routesApi.js
│   │   ├── components/         # TripForm, RouteCard, RouteComparison,
│   │   │                       # RouteMap, HeatmapPanel, States
│   │   ├── utils/              # validation, format, risk display
│   │   └── styles/main.css
│   ├── package.json
│   ├── vercel.json
│   └── .env.example
├── docs/
│   ├── REQUIREMENTS_CHECKLIST.md
│   └── LOOM_PLAN.md
├── render.yaml
└── BUILD_LOG.md
```

## 6. Prerequisites

- Python 3.12+ and Node.js 20+ / npm 10.
- Internet access for the keyless provider APIs. **No API keys are needed.**

## 7. Backend installation

```bash
cd backend
python3 -m venv ../.venv          # or any venv location
source ../.venv/bin/activate
pip install -r requirements.txt
python manage.py check
python manage.py runserver 8000
```

## 8. Frontend installation

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

## 9. Environment variable setup

All variables are optional overrides; defaults run the app locally.

Backend (`backend/.env.example`): `DJANGO_DEBUG`, `DJANGO_SECRET_KEY`,
`DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `DATABASE_URL`
(unset = SQLite; set to a `postgres://…` URL for PostgreSQL),
`NOMINATIM_BASE_URL`, `OSRM_BASE_URL`, `OPEN_METEO_BASE_URL`.

Frontend (`frontend/.env.example`): `VITE_API_BASE_URL`
(default `http://localhost:8000`).

## 10. How to run locally

1. Start the backend (step 7) on port 8000.
2. Start the frontend (step 8) on port 5173.
3. Open http://localhost:5173, keep the defaults (Chicago → St Louis) and
   choose **Generate Routes**.

## 11. API documentation

Base: `/api/v1`. All errors use one shape:
`{"error": {"code": "...", "message": "...", "fields": {"field": ["msg"]}}}`

### `GET /api/v1/health/`
→ `{"status": "ok"}`

### `POST /api/v1/routes/analyze/`
Request:
```json
{
  "origin": "Chicago, IL",
  "destination": "St Louis, MO",
  "departure_datetime": "2026-11-08T08:00:00Z",
  "load_weight_lb": 35000,
  "checkpoint_interval_miles": 25
}
```
Response (abridged):
```json
{
  "routes": [{
    "id": 1, "summary": "I-55 S",
    "distance_miles": 297.8, "duration_minutes": 268.4,
    "departure_time": "2026-11-08T08:00:00Z", "arrival_time": "2026-11-08T12:28:00Z",
    "geometry": [[41.8781, -87.6298], ["..."]],
    "checkpoints": [{
      "distance_miles": 25.0, "latitude": 41.4, "longitude": -88.1,
      "eta": "2026-11-08T08:34:00Z",
      "wind_mph": 18.2, "rain_in_per_hr": 0.0, "snow_in_per_hr": 0.0,
      "risk_level": "LOW", "risk_score": 1, "weather_available": true
    }],
    "risk_summary": {
      "low_miles": 260.0, "moderate_miles": 25.0, "high_miles": 12.8,
      "severe_miles": 0.0, "no_travel_miles": 0.0, "unknown_miles": 0.0,
      "average_risk": 1.21, "highest_risk": "HIGH", "risky_checkpoint_count": 1
    },
    "has_no_travel": false, "unsafe_reason": null
  }],
  "recommendation": {
    "route_id": 1,
    "reasons": ["Selected because it has no NO TRAVEL segments and wins the priority order…"],
    "comparison": [{"route_id": 1, "severe_miles": 0.0, "high_miles": 12.8,
                    "average_risk": 1.21, "duration_minutes": 268.4}]
  },
  "warnings": []
}
```

### `POST /api/v1/routes/heatmap/`
Powers the 0–48 h slider with real forecast data. Body:
`{geometry, departure_datetime, hour_offset (0–48), load_weight_lb,
checkpoint_interval_miles, duration_minutes?}`. The optional
`duration_minutes` is the selected route's provider duration, so
travel-time-to-point uses the same ETA method as the analysis; without it a
documented 55 mph estimate is used.
→ `{points: [{latitude, longitude, distance_miles, risk_level, risk_score,
wind_mph, rain_in_per_hr, snow_in_per_hr}], forecast_time}`

## 12. Testing instructions

```bash
# Backend — 46 tests, all external calls mocked (no network needed)
cd backend && python manage.py test && python manage.py check

# Frontend — 10 tests (validation, recommendation display, route
# selection, heatmap slider → API with mocked fetch)
cd frontend && npm test

# Lint + production build
cd frontend && npm run lint && npm run build
```

Test coverage includes: every risk threshold and exact boundary, all load
rules, highest-risk selection, missing weather → UNKNOWN, snow cm→inch
conversion, checkpoint interpolation, ETA math, risk-miles reconciliation,
recommendation priority/tie-breaks/no-travel handling, invalid API inputs,
mocked provider failure → graceful 502, and full response structure.

## 13. External API providers and limitations

| Provider | Use | Limitations |
|---|---|---|
| Nominatim (OSM) | Geocoding | Free usage policy: descriptive User-Agent required, modest rate limits; results depend on OSM place data. |
| OSRM demo server | Routing + alternatives | Public demo is best-effort with no SLA and **often returns fewer than 3 alternatives** (verified live: Chicago→St Louis returned 2). Mitigated by the detour-waypoint fallback (§14). Truck-specific restrictions (height/weight) are not modeled by the demo profile. |
| Open-Meteo | Hourly weather forecast | 16-day horizon; hourly resolution. Checkpoints beyond the horizon are reported as unknown risk, never invented. Snowfall is returned in cm and converted to inches. |

All provider calls use a 10 s timeout with one retry on transient failure,
and provider failures surface as clean 502 responses.

## 14. Deployment instructions

No accounts are created by this repo; the configuration is ready to use:

- **Backend (Render):** `render.yaml` at the repo root defines a Python web
  service: build `pip install -r backend/requirements.txt`, start
  `gunicorn config.wsgi:application` from `backend/`, with env vars for
  `DJANGO_DEBUG=false`, a generated `DJANGO_SECRET_KEY`,
  `DJANGO_ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS`. Attach a Render
  Postgres instance to get `DATABASE_URL` automatically, or keep SQLite
  for a demo.
- **Frontend (Vercel):** import `frontend/` — `vercel.json` configures the
  Vite build with SPA rewrites. Set `VITE_API_BASE_URL` to the deployed
  backend URL and rebuild.
- Verify with `python manage.py check --deploy` (run with production env
  vars set) before going live.

## 15. Known limitations and assumptions

- **ETA model:** constant average speed — checkpoint ETA = departure +
  route duration × (checkpoint distance ÷ route distance), using the
  provider's total duration. Real traffic variation is not modeled.
- **Boundary rule:** risk bands are lower-bound inclusive / upper-bound
  exclusive, except the rain (1.00 in/hr) and snow (3.0 in/hr) SEVERE tops,
  which are inclusive per the brief's wording; wind bands follow the
  whole-mph ranges as written (25–34 ⇒ ≥25 and <35).
- **Three-route fallback:** when OSRM returns fewer than 3 alternatives,
  additional genuine routes are produced by routing through offset detour
  waypoints (perpendicular offsets at ~35% and ~65% of the trip, opposite
  sides) and deduplicated. If fewer than 3 genuine routes still exist, the
  API returns what exists plus an explicit warning — routes are never
  fabricated or duplicated.
- **No-travel recommendation rule:** routes containing a NO TRAVEL segment
  rank below all clean routes; if every route has one, the least unsafe is
  recommended with an explicit warning in the reasons.
- **Unknown weather:** checkpoints outside the forecast horizon or with a
  missing measurement are `UNKNOWN` — excluded from risk-mile averages and
  reported separately as `unknown_miles`; they are never treated as safe.
- **Risk miles:** checkpoint *i*'s risk covers the segment from its
  distance to the next checkpoint; the final checkpoint (at the route end)
  covers zero miles. Known + unknown miles always reconcile to the route
  distance.
- Demo OSRM/Nominatim services are public best-effort instances; for a
  production deployment, self-host them or use a paid provider via the
  `*_BASE_URL` env overrides.
