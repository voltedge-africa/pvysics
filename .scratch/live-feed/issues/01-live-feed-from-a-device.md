# Take readings from a live device

Status: resolved (first version; not tried on hardware)
Asked: 2026-10-30. The author's ESP32 sensing unit may arrive later, so the app must be ready for it.

## What exists

- `live.py`: `parse_reading`, `LiveScorer` (one rule with dataset rows via `dataset.score_row`, arrival order, State-change
  events), `LiveLog` (every accepted reading to a CSV that imports as a dataset).
- `live_server.py`: stdlib HTTP server, `POST /reading` (object or list), `GET /status`, token in `X-Api-Key` or Bearer.
- `gui/live_controller.py`: owns server and scorer, queued signal to the GUI thread, silence watch (NO DATA), persisted settings.
- `gui/live_page.py`: the Live Feed page. Dashboard source chip and NO DATA chip; run toolbar disabled while live.
- `docs/esp32/pvysics_feed.ino`: example sketch, untested.

## Behaviour agreed in the design

- No schedule: a Sample exists only for a reading that arrived, so a midday start or a gap raises nothing.
- Silence is a separate status, not a Normal state.
- Starting a feed starts a new run; Apply and start, or a dataset replay, stops it.

## Not done / known limits

- Plain HTTP with a shared token; no TLS. One feed, one module.
- No MQTT, no serial. The transport is a seam (`LiveController._ingest`), so another can call it.
- History grows without bound for a feed left running for days.
- No ambient-to-cell temperature model; the `t` value is taken as module temperature.
- The sketch and the sensor ranges (INA219 versus the real module) are untested.
