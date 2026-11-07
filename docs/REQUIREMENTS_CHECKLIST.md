# Requirements Checklist — Weather-Aware Truck Routing (Spotter AI Assessment)

Every requirement from the assessment brief, mapped to its implementation file and
the test that verifies it. Status legend: ✅ implemented & tested · 🟡 implemented,
verified manually/smoke test only.

## 1. Stack & providers
| Requirement | Implementation | Test / evidence |
|---|---|---|
| React frontend | `frontend/` (Vite + React, JavaScript) | `npm run build` |
| Django + DRF backend | `backend/config/`, `backend/apps/` | `manage.py check` |
| Leaflet mapping | `frontend/src/components/RouteMap.jsx` (plain `leaflet`, imperative) | build + manual |
| SQLite local / PostgreSQL option | `backend/config/settings.py` (`DATABASE_URL` via dj-database-url, SQLite default) | settings import |
| Real routing API, multiple alternatives | `backend/apps/routing/providers/osrm.py` (OSRM, `alternatives=3`) | `routing/tests/test_providers.py` (mocked) |
| Real geocoding provider | `backend/apps/routing/providers/nominatim.py` (Nominatim) | `routing/tests/test_providers.py` (mocked) |
| Real weather forecast API | `backend/apps/weather/providers/open_meteo.py` (Open-Meteo); automatic backup `backend/apps/weather/providers/met_norway.py` (MET Norway) when the primary fails | `weather/tests/test_open_meteo.py`, `weather/tests/test_met_norway.py` (both mocked) |
| Providers behind replaceable modules | `providers/` packages per app; services depend on provider functions only | structure |
| No hardcoded keys; `.env.example` | All providers keyless; base URLs from env; `backend/.env.example`, `frontend/.env.example` | grep |

## 2. User inputs & validation
| Requirement | Implementation | Test / evidence |
|---|---|---|
| Origin, destination, departure datetime, load lb, interval ∈ {10,25,50} | `frontend/src/components/TripForm.jsx`; `backend/apps/routing/serializers.py` | frontend `TripForm.test.jsx`; backend `routing/tests/test_api.py` |
| Server-side validation of every field, consistent error shape `{"error": {code, message, fields}}` | `serializers.py` + `backend/apps/routing/views.py` error handler | `test_api.py::test_invalid_inputs` |
| Origin/destination must geocode, else clear 400 | `services/analysis.py` + Nominatim provider | `test_api.py::test_ungeocodable_origin` |
| Load must be positive; interval must be in set; datetime parseable | serializer field validators | `test_api.py` |
| Frontend validation + duplicate-submit prevention | `TripForm.jsx` (`utils/validation.js`, disabled submit while `loading`) | `TripForm.test.jsx` |

## 3. Route generation
| Requirement | Implementation | Test / evidence |
|---|---|---|
| THREE genuine alternatives; geometry, distance, duration, ETA, summary per route | `providers/osrm.py`, `services/analysis.py` | mocked provider tests; live smoke test |
| Never fabricate/duplicate routes | dedupe by rounded distance + geometry signature in `osrm.py` | `test_providers.py::test_dedupe` |
| Fewer than 3 from provider → genuine detour-waypoint fallback (offset points at ~35%/65%, opposite sides) | `osrm.py::fetch_routes_with_fallback` | `test_providers.py::test_fallback_adds_detour_route` |
| Still fewer than 3 → return what exists + explicit warning | `services/analysis.py` warnings list | `test_api.py` |
| Routing errors/timeouts handled gracefully | 10 s timeout + 1 retry in providers; 502 error shape in views | `test_providers.py::test_provider_failure` |

## 4. Weather checkpoint engine
| Requirement | Implementation | Test / evidence |
|---|---|---|
| Checkpoints at 0, interval, 2×interval, …, route end along actual geometry | `backend/apps/routing/services/geometry.py` (cumulative haversine + interpolation) | `routing/tests/test_geometry.py` |
| Weather at each checkpoint's ESTIMATED ARRIVAL TIME | `services/analysis.py` (ETA = departure + duration × distance fraction — constant-average-speed assumption, documented) + `weather/services/weather_service.py` | `test_geometry.py::test_eta`, `weather/tests/test_weather_service.py` |
| Wind mph, rain in/hr, snow in/hr per checkpoint | Open-Meteo hourly: `wind_speed_10m` (mph), `rain` (inch), `snowfall` (cm ÷ 2.54) | `test_open_meteo.py::test_snow_cm_to_inches` |
| Batched weather calls (comma-separated lat/lon lists), concurrent across routes | `weather_service.py`, ThreadPoolExecutor in `analysis.py` | code + smoke test timing |
| Beyond forecast horizon / missing measurement → `weather_available=false`, risk UNKNOWN (never LOW) | `weather_service.py`, `risk/services/risk.py::evaluate_checkpoint` | `risk/tests/test_risk.py::test_missing_weather_is_unknown` |

## 5. Risk classification (exact thresholds)
| Requirement | Implementation | Test / evidence |
|---|---|---|
| Wind: <25 LOW, 25–34 MOD, 35–44 HIGH, 45–54 SEV, ≥55 NO_TRAVEL | `risk/services/risk.py::classify_wind` | `risk/tests/test_risk.py` boundary tests |
| Rain: <0.10 LOW, 0.10–<0.25 MOD, 0.25–<0.50 HIGH, 0.50–1.00 SEV, >1.00 NO_TRAVEL | `classify_rain` (SEVERE band includes 1.00) | boundary tests |
| Snow: <0.5 LOW, 0.5–<1.0 MOD, 1.0–<2.0 HIGH, 2.0–3.0 SEV, >3.0 NO_TRAVEL | `classify_snow` (SEVERE band includes 3.0) | boundary tests |
| Boundary rule documented: lower bound inclusive, upper exclusive, except rain/snow SEVERE top values inclusive; wind bands as whole-mph ranges (25–34 ⇒ ≥25, <35) | docstring in `risk.py` + README §14 | — |
| Load rules: wind ≥55 → NO_TRAVEL any load; wind 45–54 & load >30,000 → NO_TRAVEL; wind 35–44 & load >40,000 → SEVERE | `evaluate_checkpoint` load overrides | `test_risk.py::test_load_rules` |
| Checkpoint risk = highest of wind/rain/snow; numeric scale LOW=1…NO_TRAVEL=5 | `risk.py` (`RISK_SCORES`) | `test_risk.py::test_highest_wins` |
| Centralized, independently unit-testable module | `backend/apps/risk/services/risk.py` (pure functions, no Django imports) | risk test module standalone |

## 6. Route risk summary
| Requirement | Implementation | Test / evidence |
|---|---|---|
| Low/Moderate/High/Severe/No-travel miles per route | `services/analysis.py::summarize_route_risk` — checkpoint *i*'s risk covers the segment from its distance to the next checkpoint; final checkpoint covers the remainder (0 if exactly at end) | `routing/tests/test_analysis.py::test_risk_miles_reconcile` |
| Unknown miles reported separately; known + unknown = total distance | `unknown_miles` in `risk_summary` | reconciliation test |
| Distance-weighted average risk (Σ segment_miles × score / known miles) | `summarize_route_risk` | `test_analysis.py` |
| Highest observed risk; risky checkpoint count (risk ≥ HIGH) | `summarize_route_risk` | `test_analysis.py` |

## 7. Recommendation engine
| Requirement | Implementation | Test / evidence |
|---|---|---|
| Lexicographic: fewest Severe miles → fewest High miles → lowest avg risk → shortest duration. No weighted score | `backend/apps/recommendations/services/recommender.py` | `recommendations/tests/test_recommender.py` incl. tie-breaks |
| NO_TRAVEL route flagged unsafe with reason; never silently recommended | `has_no_travel`, `unsafe_reason` per route; recommender ranks no-travel routes below all clean routes unless every route has them (then lexicographic among them + explicit unsafe warning in reasons) | `test_recommender.py::test_no_travel_handling` |
| Recommendation shows reasons + per-route comparison values | `recommendation.reasons`, `recommendation.comparison` in API response | `test_api.py` structure test; frontend `RouteCard` |

## 8–9. Frontend UI, map & heatmap
| Requirement | Implementation | Test / evidence |
|---|---|---|
| Dashboard: name/nav, trip form, datetime picker, load, interval selector, Generate button | `frontend/src/App.jsx`, `components/TripForm.jsx` | build |
| Three route cards, recommended highlighted, distance/duration/ETA/risk summary | `components/RouteCard.jsx`, `components/RouteComparison.jsx` | `RouteCard.test.jsx` |
| Map: all routes, distinct styles, recommended boldest, risk-colored checkpoint markers, click popups (weather+ETA+risk), auto-fit bounds, card↔map selection sync | `components/RouteMap.jsx` | build + manual |
| Heatmap: corridor risk segments for selected route + REAL 0–48 h forecast slider (backend `POST /api/v1/routes/heatmap/`), selected forecast time displayed, loading state, debounced | `components/HeatmapPanel.jsx`, `apps/weather` heatmap service in `routing/services/heatmap.py` | `HeatmapPanel.test.jsx` (slider calls API, mocked fetch) |
| Loading / error / empty states with retry | `components/States.jsx`, `App.jsx` | `TripForm.test.jsx`, build |
| No hardcoded demo route data | all data from API responses | grep |

## 10–12. Backend architecture & API
| Requirement | Implementation | Test / evidence |
|---|---|---|
| Thin views, validating serializers, services orchestrate, providers isolate externals | `backend/apps/*` layout per brief §10 | structure |
| `GET /api/v1/health/` → `{"status":"ok"}` | `routing/views.py::health` | `test_api.py::test_health` |
| `POST /api/v1/routes/analyze/` contract (routes, checkpoints, risk_summary, recommendation, warnings) | `views.py`, `serializers.py`, `services/analysis.py` | `test_api.py::test_analyze_response_structure` |
| `POST /api/v1/routes/heatmap/` contract | `views.py`, `services/heatmap.py` | `test_api.py::test_heatmap` |
| Timeouts (10 s) + one retry, structured logging, no secrets | providers (`_get_with_retry`), `settings.py` LOGGING | provider tests |
| CORS from env, DEBUG/ALLOWED_HOSTS via env, production settings path | `settings.py` | `manage.py check --deploy` output in BUILD_LOG |

## 13. Testing
| Requirement | Implementation | Test / evidence |
|---|---|---|
| Backend: thresholds+boundaries, load rules, highest-risk, missing weather, unit conversion, interpolation, ETA, risk miles, recommendation priority + no-travel, invalid inputs, provider failure, response structure — all external calls mocked | `backend/apps/*/tests/` | `python manage.py test` output in report |
| Frontend: validation, recommendation display, route selection, slider→API (mock fetch) | `frontend/src/**/*.test.jsx` (Vitest + Testing Library) | `npm test` output in report |
| Lint/format/build/checks run, failures fixed | ESLint (Vite default config), `npm run build`, `manage.py check` | outputs in report |

## 14–17. Performance, security, docs, deployment
| Requirement | Implementation | Test / evidence |
|---|---|---|
| Concurrent independent weather calls; batched coordinates; no duplicate requests | `analysis.py` ThreadPoolExecutor; one Open-Meteo call per route | smoke test |
| README with all 15 sections; `.env.example` files; `requirements.txt`; `package.json`; `.gitignore` | project root / `backend/` / `frontend/` | files |
| Loom walkthrough plan (9 points) | `docs/LOOM_PLAN.md` | file |
| Deployment prep (no accounts created): Render blueprint + Vercel static config | `render.yaml`, `frontend/vercel.json`, README §14 | `check --deploy` output |
| Live smoke test: Chicago → St Louis, interval 25, load 35,000 | real network run | results in final report + BUILD_LOG |
| Local git repo, one clean commit | project root `.git` | `git log` in report |
