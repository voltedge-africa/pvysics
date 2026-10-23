# 02: Launcher and app session

**What to build:** `uv run pvysics` opens a small launcher with Open HMI, Open Dashboard and Open both. The run (data bus, playback, history) belongs to an application session, so the HMI and the Dashboard can be opened and closed independently and closing a window does not end the run. Command-line switches choose what opens at start (HMI only, Dashboard only, both, or the launcher by default). A Dashboard opened without the HMI shows an idle message and a button to open the HMI.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] The launcher opens each window and a window that is already open is brought to the front, not duplicated.
- [ ] Closing the HMI does not stop an open Dashboard or the run; closing the launcher does not quit while another window is open; the app quits when the last window closes.
- [ ] Command-line switches select HMI only, Dashboard only or both; unknown switches give a clear usage message.
- [ ] An idle Dashboard is not blank: it explains how to start a run.
- [ ] Existing behaviour is preserved: with both windows open, one run feeds both.
- [ ] README run instructions and the demo checklist are updated.
- [ ] Offscreen smoke tests cover the launcher actions and the switches; the suite is run three times for stability (past segfaults came from cyclic GC freeing Qt windows: avoid lambdas capturing windows).
