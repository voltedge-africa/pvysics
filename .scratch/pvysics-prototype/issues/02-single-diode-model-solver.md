# 02: Single Diode Model solver

**What to build:** given a module datasheet, irradiance and temperature, the model returns the I-V and P-V curve and the maximum power point. Parameters (Iph, I0, Rs, Rsh, n) are derived from the datasheet. This is the physics core of the twin and is headless.

**Blocked by:** 01.

**Status:** ready-for-agent

- [ ] At standard test conditions (1000 W/m2, 25 C) the generic module reproduces datasheet Isc, Voc and Pmpp within 2 percent.
- [ ] Power rises with irradiance and falls with temperature in the expected direction, checked at several points.
- [ ] Zero irradiance gives zero power without errors or NaN.
- [ ] The solver handles the full voltage sweep without failing to converge.
- [ ] Parameters can be overridden for the plant (used by later tickets).
- [ ] Tests assert on observable behaviour (curve values, Pmpp), not on solver internals.
