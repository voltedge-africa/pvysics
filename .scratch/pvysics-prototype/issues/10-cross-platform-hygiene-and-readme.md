# 10: Cross-platform hygiene and README

**What to build:** confirm the prototype is genuinely multiplatform and tell the user how to run it. Remove anything platform-specific, document install and run per platform, and record the demo script from the deck as a checklist against the running app.

**Blocked by:** 06, 07, 08, 09.

**Status:** done

- [x] Code review finds no platform-specific paths, shell calls or fonts hard-coded; high-DPI scaling is enabled.
- [x] The README gives run steps for Linux, macOS and Windows using uv, plus the offscreen test command.
- [x] The README lists the demo script (setup, normal, fault, recovery, validation) matched to what the app does.
- [x] The full test suite passes offscreen on the build machine; any platform not available to test is listed honestly as untested.
- [x] A short list of known limitations and deferred items is recorded.
