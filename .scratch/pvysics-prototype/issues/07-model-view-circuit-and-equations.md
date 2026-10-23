# 07: Model view: circuit, equations and live operating point

**What to build:** a Model view in the HMI. It shows the SDM equivalent circuit schematic, the typeset equations, the parameters currently in use, and the I-V and P-V curve with the live measured operating point. The curve and operating point move as the run plays.

**Blocked by:** 02, 04.

**Status:** ready-for-agent

- [ ] The schematic and typeset equations already made for the presentation are reused from the documentation folder's assets, copied into the package so the app is self-contained.
- [ ] The parameters shown match the ones the twin uses in the current run.
- [ ] The curve is for the current measured G and T and updates as the profile plays.
- [ ] The measured operating point is drawn on the curve and sits at or below the twin's maximum power point for a healthy plant.
- [ ] The view scales sensibly on common window sizes and a high-DPI display.
- [ ] An offscreen smoke test opens the view during a run.
