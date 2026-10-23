# PV Digital Twin: glossary

Terms used by the specs, tickets and code. Use these words, not synonyms.

- **Plant**: the simulated "real" PV module. A Single Diode Model with perturbed parameters, optional faults, and sensor noise. Stands in for the physical test bench until hardware exists.
- **Twin**: the physics model of the module. A Single Diode Model with nominal datasheet parameters. It predicts power from the *measured* irradiance and temperature.
- **Single Diode Model (SDM)**: equivalent circuit of a module (photocurrent source, diode, shunt resistance Rsh, series resistance Rs) solved for current at a given voltage.
- **Module datasheet**: Isc, Voc, Impp, Vmpp, Ki, Kv, Ns. The SDM parameters are derived from it.
- **Profile**: a time series of irradiance G and ambient temperature T that drives a run.
- **Run**: one execution of a profile through plant and twin, producing samples, events and metrics.
- **Sample**: one time step of a run: G, T, measured V, I, P measured, P predicted, deviation, state.
- **Power deviation**: percentage gap between P measured and P predicted, relative to P predicted.
- **State**: Normal, Warning or Abnormal, decided from power deviation and the thresholds.
- **Threshold**: the warning limit and the abnormal limit on power deviation.
- **Mismatch**: deliberate offsets (Rs, Rsh, temperature coefficient) between plant and twin parameters so error metrics are meaningful.
- **Fault**: an injected plant condition: partial shading, soiling, series-resistance rise, bypass-diode failure, sensor drift.
- **Event**: a timestamped state change or fault change in a run.
- **Data bus**: the channel that carries samples and events from the engine to the HMI and the dashboard. In-process in the prototype.
- **HMI**: the interactive operator window: process view, model view, setup, fault injection, alarms.
- **Dashboard**: the separate read-only analytics window: KPIs, trends, validation, events.
- **Validation metrics**: MAE, RMSE and MAPE between P measured and P predicted, plus fault-detection scores (confusion matrix, detection delay, false-alarm rate).
