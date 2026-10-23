# 06: Fetch a profile from NASA POWER with options in the UI

**What to build:** on the Setup tab the user chooses fetch options (latitude and longitude, defaulting to the Site fields, start and end date, irradiance type all-sky or clear-sky, time standard) and presses Fetch. The data is requested from NASA POWER hourly point API without freezing the UI, converted to a profile with the existing validation, cached on disk, and staged as the "fetched profile" with a summary line. Errors (offline, bad dates, service error, missing values) give a clear message.

**Blocked by:** None (can start immediately).

**Status:** done

- [x] A small fetch client builds the request from the options and parses the response into a profile; it accepts an injected transport so tests never touch the network.
- [x] Clear-sky selected asks for the clear-sky shortwave parameter; all-sky asks for the all-sky one; time standard and dates appear in the request.
- [x] Option validation: latitude and longitude ranges, end not before start, a sensible maximum range, with specific messages.
- [x] The fetch runs off the UI thread with a progress indication and a Cancel or disabled button; results come back safely on the UI thread.
- [x] Results are cached in the platform's user cache location keyed by the request; a repeat fetch is served from cache without network, and the summary says so.
- [x] Offline or HTTP errors and files with missing values give clear, logged-if-available messages and leave the active profile untouched.
- [x] The fetched profile is staged (summary shown) and becomes active only via a Use fetched profile action in this ticket; ticket 07 adds the preview in front of that action.
- [x] One real fetch was done manually by the worker to confirm the live response format; the result is reported.
- [x] Bundled presets and CSV loading are unaffected.
