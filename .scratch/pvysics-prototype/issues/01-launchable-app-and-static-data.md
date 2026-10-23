# 01: Launchable app and bundled static data

**What to build:** one command opens a PyQt6 main window titled for the project, and the package ships its static inputs: a NASA POWER hourly sample for Durban (all-sky shortwave irradiance and 2 m temperature, three consecutive summer days) and a generic 60-cell, 250 W module datasheet. A profile loader turns the hourly sample into a Profile object with timestamp, G and T. This is the tracer that proves the toolchain, the data and the multiplatform GUI choice end to end.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] The data is downloaded once from NASA POWER and committed with the package, with its source and licence noted. The app needs no internet.
- [ ] The app starts from a console command defined in the project, and opens an empty main window.
- [ ] The loader returns a Profile for a chosen day; irradiance is never negative, time is increasing, and gaps or missing-value markers are rejected or filled with a clear rule.
- [ ] The datasheet loads from a data file into a typed object.
- [ ] Dependencies (PyQt6, pyqtgraph, numpy, scipy, pytest, pytest-qt) are declared in the uv project.
- [ ] An offscreen smoke test opens the window and closes it; a loader test covers the points above.
- [ ] No Qt import exists outside the GUI layer.
