# 03: Headless run: plant, twin, deviation and state

**What to build:** the highest seam. A run configuration (profile, datasheet, mismatch, sensor noise and quantisation, thresholds, seed) produces a series of Samples, Events and a state per sample. The plant is a mismatched SDM operated at its maximum power point and read through noisy sensors. The twin reads only the measured G and T and predicts power. Deviation and state follow from the thresholds.

**Blocked by:** 02.

**Status:** done

- [x] A healthy run on the bundled profile stays Normal with the default thresholds and mismatch, and its deviation is small and non-zero.
- [x] With zero mismatch and zero noise the deviation is zero; with mismatch or noise it is not, so the model comparison is meaningful.
- [x] The same seed gives identical results; a different seed changes the noise.
- [x] Night-time samples (near zero irradiance) do not produce spurious deviation or state flapping.
- [x] State changes are emitted as Events with timestamps.
- [x] The run API has no Qt dependency and can be called from a test or a script.
- [x] Tests exercise the run API only.
