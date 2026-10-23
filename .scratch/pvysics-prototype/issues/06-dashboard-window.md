# 06: Dashboard window

**What to build:** a second, read-only window that subscribes to the same data bus. It shows KPI tiles (P measured, P predicted, deviation, state, energy), a measured-vs-predicted power chart, a deviation chart with warning and abnormal bands, an irradiance and temperature chart, and an event log of state and fault changes.

**Blocked by:** 05.

**Status:** ready-for-agent

- [ ] The app opens the Dashboard alongside the HMI, and both update from one run.
- [ ] The Dashboard has no controls that change the run.
- [ ] The deviation chart draws the warning and abnormal bands at the current thresholds.
- [ ] Injecting a fault in the HMI shows up in the Dashboard's charts and event log.
- [ ] Charts stay responsive over a full day of samples.
- [ ] Closing the Dashboard does not stop the HMI, and it can be reopened.
- [ ] An offscreen smoke test runs a short run with a fault and checks the event log has entries.
