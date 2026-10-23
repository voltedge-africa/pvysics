# 07: Preview a fetched profile before loading it

**What to build:** after a fetch, the user sees a preview of the staged profile before it can be used: G and T charts over the whole range and summary statistics (sample count, date range, peak G, mean T, and the validation checks). Two actions: Use profile (makes it the active profile) and Discard (drops it). Nothing replaces the active profile until Use.

**Blocked by:** 06.

**Status:** done

- [x] The preview shows both charts and the statistics for the staged profile, themed with the active palette.
- [x] Statistics come from a headless helper with tests (known profile in, known numbers out).
- [x] Use profile makes the staged profile active and it appears in the run summary; the next Apply and start uses it.
- [x] Discard removes the staged profile and the previous active profile stays.
- [x] A fetch that fails or fails validation never reaches the preview.
- [x] The preview handles a multi-day range (charts stay responsive and readable).
- [x] Offscreen smoke test: fetch with a fake transport, preview, use, apply, start.
