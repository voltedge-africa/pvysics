# 03: Log pane at the bottom of each window

**What to build:** a log pane docked at the bottom of the HMI and of the Dashboard showing what the app is doing, line by line with time, level and message. Key actions log at sensible levels: run started, paused, reset, speed changed, setup validated and applied, fault injected or cleared, state changes and alarms, rejected CSV or datasheet, validation started and finished, export done, errors. The pane has a level filter, Clear and Copy.

**Blocked by:** 02.

**Status:** done

- [x] Standard Python logging feeds one log model shared by both windows; a headless test covers levels, ordering and a bounded size.
- [x] The pane sits at the bottom of both windows, can be collapsed, and is themed (works with ticket 01's palettes if present).
- [x] A rejected CSV or datasheet, and a failed action, appear as warning or error lines with the specific message.
- [x] The level filter hides lower-level lines without losing them; Clear empties the pane; Copy puts the visible text on the clipboard.
- [x] Logging from the engine side does not import Qt; the Qt handler lives in the GUI layer and is thread-safe (validation and fetch run in worker threads).
- [x] Offscreen smoke test: applying a setup and injecting a fault produce log lines in both windows.
