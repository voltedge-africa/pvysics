# Spec: pvysics UI iteration (themes, launcher, logs, live charts, configurable inputs)

**Status:** ready-for-agent

Follow-up to the prototype in `.scratch/pvysics-prototype/`. Same rules: PyQt6, multiplatform, headless engine with no Qt, vertical-slice tickets, tests at the highest seam.

## Problem Statement

The prototype works but is awkward to present and to configure. The Dashboard has few live charts, and charts are always black, which is unreadable next to a light desktop. There is no log of what the app is doing. The module datasheet and the input profile cannot be changed from the UI beyond loading files, and there is no way to fetch a profile for a chosen place and dates. The app opens both windows at once with no way to start just one.

## Solution

Six changes, each shippable on its own:

1. Light and dark themes that follow the system by default, with a manual override. Every view, chart, schematic and equation is legible in both.
2. A launcher that opens the HMI, the Dashboard, or both, independently, plus command-line switches.
3. A log pane at the bottom of each window, showing what the app is doing, with levels.
4. More live charts on the Dashboard.
5. Editable datasheet parameters on the Setup tab with a button that resets to the generic module.
6. Fetch a profile from NASA POWER with options chosen in the UI, and preview it before loading it.

## User Stories

1. As a presenter, I want the app to follow my system's light or dark setting, so that it matches the room and my other windows.
2. As a presenter, I want to force light or dark from a menu, so that I can fix it for a projector.
3. As a presenter, I want my theme choice remembered, so that I do not set it every time.
4. As a viewer, I want charts to have a light background in light mode, so that they are readable on a white slide or desktop.
5. As a viewer, I want the circuit schematic and equations legible in dark mode, so that no view is unreadable.
6. As a viewer, I want state colours (green, amber, red) to stay recognisable in both themes, so that the state is always clear.
7. As a presenter, I want a launcher with Open HMI, Open Dashboard and Open both, so that I choose what to show.
8. As a presenter, I want to open and close the HMI and the Dashboard independently, so that I can show one on a second screen.
9. As a presenter, I want command-line switches for HMI only, Dashboard only or both, so that I can script the start.
10. As an operator, I want the Dashboard to say what to do when no run is going, so that an empty window is not confusing.
11. As an operator, I want a log pane at the bottom of each window, so that I see what the app is doing without a terminal.
12. As an operator, I want log lines with time, level and message, so that I can follow events and errors.
13. As an operator, I want to filter the log by level and clear it, so that I can focus on warnings and errors.
14. As an operator, I want errors such as a rejected CSV or a failed fetch to appear in the log, so that I know why something did not happen.
15. As a researcher, I want to copy the log text, so that I can paste it into a report or a bug.
16. As an observer, I want live charts for voltage and current, so that I see the electrical state.
17. As an observer, I want a live I-V and P-V curve with the operating point on the Dashboard, so that I see where the module operates.
18. As an observer, I want a cumulative energy chart, so that I see production build up.
19. As an observer, I want a histogram of power deviation, so that I see its spread.
20. As an observer, I want time spent in each state, so that I see how often the system was Normal, Warning or Abnormal.
21. As a researcher, I want to edit Isc, Voc, Impp, Vmpp, Ki, Kv and Ns in the UI, so that I can model my own module.
22. As a researcher, I want a Reset to generic module button, so that I can recover the defaults in one click.
23. As a researcher, I want impossible datasheet values rejected with a clear message, so that the twin never runs on nonsense.
24. As a researcher, I want to choose the place, date range and irradiance type (all-sky or clear-sky) for a fetch, so that I get the data I need.
25. As a researcher, I want to use the Setup site fields as the default fetch location, so that I do not retype coordinates.
26. As a researcher, I want fetching to run without freezing the window, so that I can keep working.
27. As a researcher, I want a clear message when I am offline or the service fails, so that I know what happened.
28. As a researcher, I want fetched data cached locally, so that I do not download the same data twice.
29. As a researcher, I want to preview a fetched profile as a chart with its statistics before loading it, so that I can check it is the data I wanted.
30. As a researcher, I want to discard a previewed profile, so that a bad fetch never replaces my current profile.

## Implementation Decisions

- **Theme:** a single palette object per theme (window, text, chart background, chart foreground, grid, band colours, state colours). Qt's own colour scheme is the source of truth for "system". The override is stored with Qt's platform-neutral settings store. Chart widgets read the palette and re-apply it when the theme changes. Pre-rendered design images (schematic, equations) get a dark-mode treatment at load time, not new files per theme, unless that proves impossible.
- **Launcher and session:** one process. The run (data bus and playback) belongs to an application-level session, not to a window, so the HMI and the Dashboard can open and close independently. Closing a window never ends the session; quitting does. Command-line switches pick which windows open at start; the default opens the launcher.
- **Dashboard without the HMI:** the run is controlled only from the HMI. A Dashboard opened alone shows an idle message and a way to open the HMI.
- **Logs:** standard Python logging. One handler feeds a log model that both windows' panes display. The pane is a bottom dock in each window with level filter, clear and copy. Existing key actions (setup applied, run started, paused, reset, fault injected or cleared, alarms, profile or datasheet rejected, validation, fetch) log at sensible levels.
- **New Dashboard charts:** voltage and current; live I-V and P-V with the operating point; cumulative energy; deviation histogram; time in each state. All update at the UI tick rate with bounded work, as the existing charts do.
- **Datasheet editing:** the Setup tab edits the same typed datasheet the engine uses. Validation rules: all values positive, Vmpp below Voc, Impp below Isc, Ns a positive integer, and the diode-fit must succeed. Reset restores the generic module.
- **Fetching:** NASA POWER hourly point API, the same source as the bundled sample. Options in the UI: latitude and longitude (default from the Setup site), start and end date, irradiance type (all-sky or clear-sky shortwave), time standard (local standard or UTC). Network access goes through one small client that can be given a fake transport in tests. A fetch runs off the UI thread. Results are cached on disk in the platform's user cache location, keyed by the request. This reverses the earlier "no live fetching" decision; the bundled data stays as the offline default and fallback.
- **Preview:** a fetched profile is staged, not active. A preview shows G and T charts and summary statistics (sample count, date range, peak G, mean T) and the validation checks already used for CSV files. Use profile makes it the active profile; Discard drops it.

## Testing Decisions

- **Seams:** the fetch client with a fake transport (parsing, options to request, errors, caching), the theme palette as plain data, the log model, and the existing headless run. GUI behaviour gets offscreen smoke tests, as before.
- **No network in the test suite.** A worker may do one manual real fetch to confirm the live format and report it.
- **Good test:** observable behaviour only, for example "a fetch with clear-sky selected asks for the clear-sky parameter", "the log pane shows an error line after a rejected CSV", "dark and light palettes both give a chart contrast above a stated ratio".
- **Prior art:** the existing pytest and pytest-qt tests.

## Out of Scope

- Other data sources (PVGIS and so on), plane-of-array irradiance, sun position.
- Per-theme rewritten design assets by hand.
- Multi-process or networked Dashboard.
- Log persistence to disk and log rotation.
- Installers.

## Further Notes

- "Logs ... in a pane at the bottom of the window" is read as an application log pane in each window. If a different log was meant, say so.
- Tickets are numbered per this feature. Blocking edges are in each file.
