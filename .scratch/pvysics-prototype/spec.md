# Spec: PV digital twin desktop prototype (pvysics)

**Status:** ready-for-agent

## Initiative

Build a runnable, cross-platform desktop prototype of the PV digital twin that was designed in the `documentation` folder (wireframes, diagrams, deck). No hardware exists, so a simulated plant stands in for the physical bench. All input data is static: a bundled sample from NASA POWER and a generic module datasheet.

**Success looks like:** on Linux, macOS and Windows, one command opens an HMI window and a Dashboard window. The presenter runs the five-step demo from the deck: setup, normal operation, inject a fault and watch the state go Abnormal, recover, then read the validation metrics.

**Hard rule from the user:** the GUI uses PyQt, with the aim of running on every major platform.

**How the work is organised:** this spec holds the stories. Ten tracer-bullet tickets under `issues/` deliver them. Each ticket is one fresh-context unit of work, ordered by blocking edges.

## Problem Statement

A student presenting a physics-informed digital twin for PV state estimation has a Simulink model and a set of wireframes, but nothing runnable that shows the twin and plant side by side. The physical bench cannot be built yet, so there is no way to demonstrate the idea, tune thresholds, or produce MAE, RMSE and MAPE numbers.

## Solution

A desktop application with two windows that read the same simulated run. The HMI shows the plant and the twin side by side, lets the operator inject faults, and shows alarms. The Dashboard shows trends, KPIs, events and validation results. A model view shows the Single Diode Model circuit, its equations and its live operating point. A setup screen chooses the input profile, module parameters, plant-vs-twin mismatch, sensor noise and thresholds.

## User Stories

1. As a presenter, I want one command that opens the HMI and the Dashboard, so that I can start a demo quickly on any laptop.
2. As a presenter, I want the app to run on Linux, macOS and Windows, so that I am not tied to one machine.
3. As a presenter, I want a bundled clear-day profile for Durban, so that the demo works with no internet.
4. As a presenter, I want the profile played back at an adjustable speed, so that a full day fits in a few minutes.
5. As an operator, I want to start, pause and reset a run, so that I control the demo.
6. As an operator, I want to see the plant's irradiance, temperature, voltage, current and measured power, so that I know what the system is producing.
7. As an operator, I want to see the twin's predicted power next to the measured power, so that I can compare them.
8. As an operator, I want to see power deviation as a gauge with warning and abnormal bands, so that I see how far off the plant is.
9. As an operator, I want a state banner that reads Normal, Warning or Abnormal in green, amber or red, so that I can read the system state at a glance.
10. As an operator, I want to inject partial shading, soiling, a series-resistance rise, a bypass-diode failure or sensor drift, so that I can show the twin detecting problems.
11. As an operator, I want a single button that clears all faults, so that I can recover and repeat the demo.
12. As an operator, I want an alarm list with time, severity and cause, so that I can see what happened and acknowledge it.
13. As an operator, I want to acknowledge an alarm, so that I can show the workflow.
14. As an operator, I want to see the SDM equivalent circuit and its equations, so that the model is visible and not hidden.
15. As an operator, I want to see the model's I-V and P-V curve with the measured operating point, so that I see how G and T move the curve.
16. As an operator, I want to see the model parameters in use, so that I know what the twin assumes.
17. As a researcher, I want to choose a preset profile or load my own CSV of timestamp, G and T, so that I can test other conditions.
18. As a researcher, I want column mapping and file checks when loading a CSV, so that a bad file is rejected with a clear message.
19. As a researcher, I want to load a module datasheet from a file or use the generic module, so that the twin matches the module I study.
20. As a researcher, I want to set plant-vs-twin mismatch for Rs, Rsh and the temperature coefficient, so that the error metrics mean something.
21. As a researcher, I want to set sensor noise and quantisation levels, so that the simulated measurements look like real ones.
22. As a researcher, I want runs to be repeatable from a seed, so that results can be reproduced.
23. As a researcher, I want the warning and abnormal limits set by hand or derived from a healthy run, so that thresholds are justified by data.
24. As an observer, I want a separate read-only Dashboard window, so that I can show analytics next to the HMI.
25. As an observer, I want KPI tiles for measured power, predicted power, deviation, state and energy, so that I get the headline numbers.
26. As an observer, I want a measured-vs-predicted power chart, so that I can see tracking over time.
27. As an observer, I want a deviation chart with warning and abnormal bands, so that I see when limits are crossed.
28. As an observer, I want an irradiance and temperature chart, so that I can relate power to conditions.
29. As an observer, I want an event log of state and fault changes, so that I can see the timeline.
30. As a researcher, I want MAE, RMSE and MAPE on a healthy run, so that I can report model accuracy.
31. As a researcher, I want fault-detection results with a confusion matrix, detection delay and false-alarm rate, so that I can report state-estimation quality.
32. As a researcher, I want to export samples and metrics to CSV, so that I can use them in a report.
33. As a developer, I want the engine to run headless, so that it can be tested and later fed by an ESP32 instead of the simulated plant.
34. As a developer, I want clear run instructions per platform, so that anyone can start the app.

## Implementation Decisions

- **GUI toolkit:** PyQt6, for a native look on Linux, macOS and Windows. Charts use pyqtgraph, which targets PyQt6. This is the one fixed constraint.
- **Packaging:** the existing uv project, `pvysics`, with a console entry point that launches the app. No platform-specific code. File locations use platform-neutral path handling.
- **Engine and GUI are separate.** The engine is a headless module with no Qt imports. The GUI is a thin layer that drives it with a timer and renders its output.
- **Data bus:** in-process Qt signals carry samples and events from the engine to both windows. This stands in for the WebSocket and CSV bus in the design. The same sample record is what an ESP32 would publish later.
- **Plant and twin are separate models.** The plant has perturbed parameters, faults and sensor noise. The twin has nominal parameters and reads only the measured G and T.
- **SDM solver:** numpy and scipy, solving the implicit current equation. Parameters are derived from the module datasheet. The generic module is a 60-cell, 250 W module.
- **Fault models:** partial shading lowers photocurrent on part of the module. Soiling scales effective irradiance. Series-resistance rise increases Rs. Bypass-diode failure drops a group of cells. Sensor drift biases the measured irradiance that the twin sees, so it produces a false deviation.
- **State estimator:** deviation compared with the warning and abnormal limits. Thresholds can be derived from a healthy run as mean plus 2 and 3 standard deviations of deviation.
- **Static data:** one hourly sample from NASA POWER for Durban (all-sky shortwave irradiance and 2 m temperature), downloaded once and bundled with the app, plus a generic datasheet. The engine interpolates hourly data to the step the run needs. Live fetching is not part of the prototype.
- **Reproducibility:** all randomness uses a seed carried in the run configuration.
- **Reuse of design assets:** the circuit schematic and typeset equations already produced for the deck are reused in the model view.

## Testing Decisions

- **One seam, the highest available:** the headless run. Configuration in (profile, datasheet, mismatch, noise, thresholds, scheduled faults, seed), samples, events and metrics out. Tests exercise this and assert on external behaviour only.
- **Good test:** states what a user or the demo would observe, for example "shading drives the state to Abnormal within N samples" or "a healthy run's MAPE is under a stated bound". It does not assert on internals.
- **Physics checks:** the twin reproduces datasheet Isc, Voc and Pmpp at standard test conditions within a stated tolerance.
- **GUI:** one smoke test per window, run offscreen, that opens the window and processes a short run without error. No pixel tests.
- **Prior art:** none in this repo yet. Use pytest and pytest-qt.

## Out of Scope

- Real hardware, ESP32 firmware and serial or Wi-Fi links.
- Live NASA POWER or PVGIS fetching, and sun-position or plane-of-array irradiance calculations.
- A web UI, a WebSocket server or any network service.
- Multiple modules, strings or arrays; MPPT or load modelling.
- Machine-learning fault classification.
- Installers and code signing. A documented run-from-source path is enough.

## Further Notes

- Design sources: the wireframes, block diagrams and deck in the documentation folder. Placeholder numbers in the wireframes are not requirements.
- Default site for the bundled data: Durban, matching the department.
- Status line, triage and blocking edges follow the local tracker conventions.
