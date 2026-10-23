# 08: Setup screen

**What to build:** a Setup view in the HMI. The user selects a preset profile or loads a CSV (timestamp, G, T) with column mapping and file checks, loads a module datasheet file or picks the generic module, sets mismatch (Rs, Rsh, temperature coefficient), sensor noise and quantisation, the seed, and the thresholds (manual or derived from a healthy run). A site block (latitude, longitude, tilt, azimuth) is stored with the run as metadata only. Validate then Apply and start.

**Blocked by:** 04.

**Status:** ready-for-agent

- [ ] The bundled profile days appear as presets.
- [ ] A valid CSV loads; a CSV with a missing column, non-numeric values, decreasing time or negative irradiance is rejected with a specific message and the previous profile stays active.
- [ ] A datasheet file loads; a malformed one is rejected with a message.
- [ ] Changing mismatch, noise, seed or thresholds changes the next run and nothing is applied until Apply and start.
- [ ] Derive thresholds runs a healthy run and fills warning and abnormal limits from its deviation statistics; the values are shown and can be edited.
- [ ] Site fields are saved and shown in the run summary but do not alter the physics.
- [ ] Settings use sensible defaults and Reset to defaults works on every platform's file paths.
- [ ] An offscreen smoke test applies a changed setup and starts a run.
