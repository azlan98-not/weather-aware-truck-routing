# Loom Walkthrough Plan (5–10 minutes)

Target length ~8 minutes. Record with the backend on `:8000` and the
frontend on `:5173`, browser zoomed to 110%.

| # | Segment (≈ time) | Show | Say |
|---|---|---|---|
| 1 | Intro (0:00–0:40) | App landing page | "Weather-Aware Truck Routing for the Spotter assessment: it compares real route alternatives by the weather the truck will actually meet at each checkpoint's arrival time." |
| 2 | Architecture & stack (0:40–1:40) | README architecture diagram + repo tree | React + Leaflet frontend; Django REST backend in layers — thin views, serializers, services, providers. Nominatim geocodes, OSRM routes, Open-Meteo forecasts — all keyless, all behind provider modules. Risk and recommendation engines are pure, centralized modules. |
| 3 | Enter a trip (1:40–2:30) | Trip form | Origin Chicago, destination St Louis, departure tomorrow 08:00, load 35,000 lb, checkpoints every 25 miles. Note frontend validation; clear a field to show an inline error, then submit. Mention the button disables while processing. |
| 4 | Three alternatives (2:30–3:20) | Route cards + warnings area | Three genuine routes from OSRM. Point out the warning if the provider returned fewer and the detour-waypoint fallback supplied a real alternative — routes are never duplicated or invented. |
| 5 | Compare risk (3:20–4:20) | Route cards' stats + risk bars | Distance, duration, ETA, severe/high/no-travel miles, distance-weighted average risk, risky checkpoint count. Explain the segment rule behind risk miles and that unknown miles are reported separately — never counted as safe. |
| 6 | Inspect checkpoints (4:20–5:20) | Map; click the selected route and a checkpoint marker | Checkpoint popup: ETA at that point, wind/rain/snow at that hour, risk level. Stress: weather is the forecast for the truck's estimated arrival, using the constant-average-speed model. Show marker colors and card↔map selection sync. |
| 7 | Recommendation (5:20–6:10) | Recommended card's "Why this route?" | The lexicographic priority — fewest severe miles, then high miles, then average risk, then duration — and how a NO TRAVEL route would be flagged unsafe and ranked below clean routes. |
| 8 | Heatmap slider (6:10–7:10) | Heatmap panel; drag 0h → 24h → 48h | The slider calls a real backend endpoint that re-evaluates forecast weather at departure + offset + travel time to each point; show the corridor colors and displayed forecast time change. Nothing is simulated client-side. |
| 9 | Backend & tests (7:10–8:00) | Terminal + `apps/risk/services/risk.py` briefly | Show the risk engine thresholds and load rules, then run `python manage.py test` (46 tests) and `npm test` (10 tests) — all green, all external calls mocked. Close with the README's limitations section. |
