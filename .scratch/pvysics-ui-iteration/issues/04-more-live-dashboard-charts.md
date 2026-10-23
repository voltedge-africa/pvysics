# 04: More live Dashboard charts

**What to build:** the Dashboard Overview gains five live views alongside the existing ones: voltage and current, a live I-V and P-V curve with the operating point, cumulative energy, a histogram of power deviation, and time spent in each state. All update during the run at the UI tick rate with bounded work, and follow the active theme.

**Blocked by:** 01.

**Status:** ready-for-agent

- [ ] Each of the five charts exists and updates while a run plays; Reset clears them; reopening the Dashboard shows history so far.
- [ ] The layout stays readable at common window sizes (a scrollable or tabbed arrangement is fine), with the existing KPI tiles and charts intact.
- [ ] The curve, histogram and state-time numbers come from headless helpers that have tests (for example "time in state sums to the elapsed time").
- [ ] Update cost per tick is bounded, asserted by sample counts not wall-clock time.
- [ ] Charts use the theme palette; screenshots in both themes were checked.
- [ ] An offscreen smoke test runs a short run with a fault and checks the new charts have data.
