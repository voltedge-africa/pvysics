# 05: Fault injection and alarms

**What to build:** the five faults can be injected from the HMI and cleared with one button. Each fault changes the plant in the way described in the spec. Alarms appear in a list with time, severity and a probable cause, and can be acknowledged. The engine accepts scheduled and live faults.

**Blocked by:** 04.

**Status:** ready-for-agent

- [ ] Partial shading, soiling, series-resistance rise and bypass-diode failure each lower the plant's measured power while the twin's prediction stays at the healthy value.
- [ ] Sensor drift makes the twin's prediction wrong (a false deviation) while true plant power is unchanged.
- [ ] Injecting a clear fault at mid-day drives the state to Abnormal within a stated, short delay; Clear all returns it to Normal.
- [ ] Each state transition adds an alarm with time, severity and a cause that names the active fault, or "unknown" when none.
- [ ] An alarm can be acknowledged; unacknowledged alarms are visibly distinct.
- [ ] Faults are available through the headless run API as a schedule, so they can be tested without the GUI.
- [ ] Tests cover each fault's observable effect and the Clear all behaviour.
