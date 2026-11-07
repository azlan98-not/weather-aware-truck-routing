# Loom Walkthrough — Word-for-Word Script (~8 minutes)

Read the **Say** lines exactly as written; they are timed to about 8 minutes
at a natural pace. Do the **Show / Click** actions while speaking.
Record against the deployed app if hosting is live, otherwise run the
backend on `:8000` and the frontend on `:5173`, browser zoom 110%.

Demo trip used throughout: **Chicago → St Louis**, departure **tomorrow
08:00**, load **35,000 lb**, checkpoints every **25 miles**.

## ⚠️ Free-plan split (Loom Starter caps recordings at 5:00)

Record this as **two Looms**, each safely under 5 minutes:

- **Part 1** — sections 1–6 (Intro → Inspect checkpoints), ~4:45.
  End Part 1 after section 6 with: "…and in part two, the recommendation
  and the heatmap." Post the Part 2 link in Part 1's description.
- **Part 1 link goes in the questionnaire** (with Part 2 linked from it),
  unless the questionnaire offers a second video field — then use both.
- **Part 2** — sections 7–9 (Recommendation → close), ~3:15.
  Open Part 2 with: "Part two: how the recommendation works."

Timings below are the combined ~8 minutes; the split points keep each
part under the cap with margin. Do not try to squeeze it into one take —
the free recorder hard-stops at 5:00, mid-sentence if you're unlucky.

---

## 1 — Intro (0:00–0:40)

**Show:** the app's landing page, form empty.

**Say:** "Hi, I'm Azlan Asif, and this is my submission for the Spotter AI
full-stack assessment: Weather-Aware Truck Routing. The idea is simple —
a truck shouldn't just take the fastest route; it should take the route
where the weather it will actually meet, at the time it actually gets
there, is safest for its load. So this app compares real route
alternatives, samples the forecast weather along each one, scores the
risk, and recommends the safest route — with the reasons shown."

## 2 — Architecture and stack (0:40–1:40)

**Show:** the GitHub repo — README architecture section, then the folder tree.

**Say:** "Quick look at the architecture. The frontend is React with
Leaflet for the map. The backend is Django with Django REST Framework,
organised in layers: thin views, serializers that validate, services that
hold the business logic, and providers that talk to the outside world.
Three external services, all free and keyless: Nominatim geocodes the
place names, OSRM provides the routing, and Open-Meteo provides the
forecasts. Because every provider sits behind its own module, any of them
can be swapped without touching the business logic. The risk engine and
the recommendation engine are pure, centralised modules — the rules exist
in exactly one place, and they're unit-tested directly."

## 3 — Enter a trip (1:40–2:30)

**Show:** the trip form. Type the demo trip in as you speak.

**Say:** "Here's the trip form. Origin: Chicago. Destination: St Louis.
Departure: tomorrow at 8 AM. Load weight: thirty-five thousand pounds.
And weather checkpoints every twenty-five miles — ten and fifty are also
available. Validation runs on both the frontend and the backend. If I
clear a required field…"

**Click:** clear the load field briefly — the inline error appears — then restore `35000`.

**Say:** "…I get an inline error immediately. And while a request is
running, the button disables itself so I can't submit twice. Let's
generate the routes."

**Click:** *Generate Routes*.

## 4 — Three alternatives (2:30–3:20)

**Show:** the route cards and the map as results load.

**Say:** "We get three genuine route alternatives from OSRM. One honest
detail: OSRM's public server doesn't always return three alternatives
directly. When it returns fewer, the backend generates additional real
alternatives by routing through detour waypoints — and the response
carries a warning saying exactly that, which you can see here. Routes are
never duplicated or invented just to make the number three."

## 5 — Compare risk (3:20–4:20)

**Show:** the route cards' stats and risk-mile bars; move slowly across all three.

**Say:** "Each card shows distance, duration, estimated arrival, and the
risk breakdown in miles: low, moderate, high, severe, and no-travel. The
miles come from a segment rule — each checkpoint's risk applies to the
stretch of road from that checkpoint to the next one — so the categories
add up exactly to the route distance. The average risk is weighted by
distance, not just averaged across checkpoints. And if weather data is
ever missing at a checkpoint, those miles are reported separately as
unknown. Missing weather is never silently treated as safe weather."

## 6 — Inspect checkpoints (4:20–5:20)

**Show:** the map. Click the selected route, then click one checkpoint marker — the popup opens.

**Say:** "On the map, every checkpoint is a marker coloured by its risk
level. This popup is the heart of the app: it shows the truck's estimated
arrival time at this exact point, and the forecast wind, rain, and snow
for that hour — not for the departure time. Arrival times are calculated
from cumulative distance along the real route geometry, using the
provider's total duration, so it's a constant-average-speed model, and
that's documented in the README. Clicking a card and clicking the map
stay in sync, so I can inspect either way."

## 7 — Recommendation (5:20–6:10)

**Show:** the recommended card and its "Why this route?" section.

**Say:** "This route is marked recommended, and the app shows its working.
The priority is lexicographic, exactly as specified: fewest severe miles
first, then fewest high miles, then the lowest average risk, then the
shortest travel time. No weighted score hiding the trade-offs. And if a
route contains a no-travel checkpoint — say, wind over fifty-five miles
per hour — it's flagged unsafe with the reason, and it ranks below every
route without one. On a calm day like this demo, all three tie on risk,
so the shortest duration wins."

## 8 — Heatmap slider (6:10–7:10)

**Show:** the heatmap panel. Drag the slider 0h → 24h → 48h, pausing at each stop.

**Say:** "Finally, the corridor heatmap. This slider runs from departure
to forty-eight hours out. It isn't a client-side simulation — every move
calls a backend endpoint that re-evaluates the forecast at departure,
plus the offset, plus the travel time to each point along the corridor,
and recolours the segments. You can see the forecast time and the colours
update with real data as I drag it."

## 9 — Backend, tests, close (7:10–8:00)

**Show:** the code editor on `backend/apps/risk/services/risk.py`, then a terminal.

**Say:** "A quick look under the hood: this is the risk engine — the
wind, rain, and snow thresholds from the brief, including the load rules:
fifty-five mile-per-hour wind is no-travel at any load; forty-five to
fifty-four with a load over thirty thousand pounds is also no-travel; and
thirty-five to forty-four with over forty thousand pounds is severe."

**Click:** run `python manage.py test`, then `npm test`.

**Say:** "And the tests: forty-six backend tests and ten frontend tests,
all passing, with every external API mocked so they're repeatable. The
README documents the API, the providers and their limitations, and the
assumptions — including the ones I just mentioned. Thanks for watching."

---

## Before you press record

- [ ] App open (deployed URL, or local `:5173`), backend healthy.
- [ ] Demo trip values ready: Chicago → St Louis, tomorrow 08:00, 35,000 lb, 25-mile checkpoints.
- [ ] Tabs ready: app, GitHub README, `risk.py`, terminal with test commands typed.
- [ ] Close notifications; mic check with a 10-second test recording.
- [ ] One take is fine — small stumbles are normal and human.
