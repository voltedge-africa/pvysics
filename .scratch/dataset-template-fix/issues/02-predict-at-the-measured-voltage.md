# Imported datasets are predicted at the maximum power point, not at the measured voltage

Status: resolved
Found: 2026-10-30, from the lecturer's mid-term comment (evaluate the SDM at the measured terminal voltage, or state that an MPPT is used)

## Change

- `single_diode.power_at_voltage` gives V times the SDM current at a voltage.
- `analyse_dataset` predicts a row with a voltage at that voltage; a row without one (a power-only file) is predicted at the
  maximum power point. The module's maximum power per row is kept in `DatasetReport.mpp_power_w` and exported as `mpp_power_w`.
- A simulated run still reads the plant at its own maximum power point and predicts the maximum power: an ideal-tracker
  assumption, now stated in the manual and README.
- Validation reports each fault's mean deviation and the healthy run's baseline offset (Analysis screen and metrics CSV).
- Charts no longer rescale axis values with an SI prefix (a time axis read "(x0.001)").

## Known limits

- The daylight rule is unchanged: a row whose predicted power is under 5 W counts as night. At the measured voltage that
  prediction can be small for a module held near 0 V or open circuit by day, so such a row is not scored.
- No ambient-temperature model: the temperature column is taken as module temperature.
- The ideality factor n is fixed at 1.3 (the mid-term report's Simulink model used 1.2); to be decided with the author.
