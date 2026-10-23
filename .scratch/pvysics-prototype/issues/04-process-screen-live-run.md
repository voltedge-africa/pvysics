# 04: HMI process screen with live run

**What to build:** the HMI window's Process view. A run plays back in real time at an adjustable speed. The screen shows the plant's measured values, the twin's predicted power, the deviation gauge with the warning and abnormal bands, and the colour-coded state banner. Start, Pause and Reset work. Samples reach the screen through the in-process data bus.

**Blocked by:** 03.

**Status:** ready-for-agent

- [ ] Start plays the bundled profile, Pause freezes it and Reset returns to the start.
- [ ] A speed control changes playback rate without restarting the run.
- [ ] Plant G, T, V, I and P measured, and twin P predicted, update on every sample.
- [ ] The deviation gauge and the banner follow the sample state, green, amber and red.
- [ ] The data bus is a single object that other windows can subscribe to.
- [ ] The UI stays responsive at the fastest speed setting.
- [ ] An offscreen smoke test plays a short run through the window and sees the banner and values change.
