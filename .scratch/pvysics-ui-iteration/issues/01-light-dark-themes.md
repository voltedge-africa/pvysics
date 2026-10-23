# 01: Light and dark themes

**What to build:** the app follows the system light or dark setting by default and offers a manual override (System, Light, Dark) in a View menu. Every view in both windows is legible in both themes: window and widget colours, all pyqtgraph charts (background, axes, grid, curves, deviation bands), the state banner and gauge, the circuit schematic and the typeset equations. The choice is remembered across runs.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] A palette per theme exists as plain data, with a headless test that text-on-background and chart-foreground-on-chart-background contrast exceed a stated ratio in both themes.
- [ ] System, Light and Dark choices work; System follows the OS setting and reacts when it changes while running.
- [ ] Charts have a light background in light mode and a dark one in dark mode, in the Process, Model and Dashboard views (including the Validation tab's widgets).
- [ ] The circuit schematic and equation images are legible in dark mode (white-on-transparent or equivalent), without adding hand-made duplicate files unless unavoidable.
- [ ] State colours stay recognisable (green, amber, red) in both themes.
- [ ] The theme choice persists using Qt's platform-neutral settings store.
- [ ] Offscreen screenshots of each tab in both themes were rendered and checked; paths are given in the report.
- [ ] No regression in the existing tests; offscreen smoke test switches theme with all windows open.
