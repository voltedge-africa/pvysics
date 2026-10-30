// PV Digital Twin: Tutorial Handbook (Typst source). The written companion to the six tutorial videos in tutorials/.
//
// Build from the repository root (see manual-style.typ):
//
//   tutorials/.venv/bin/python -W ignore tutorials/figures.py       # the figures, from the app's own engine
//   typst compile --root . --font-path src/pvysics/gui/fonts docs/tutorial-handbook.typ docs/tutorial-handbook.pdf
//
// The PDF is generated and not tracked (see .gitignore).

#import "manual-style.typ": *
#show: manual.with(
  version: "0.3.0",
  doc-title: "PV Digital Twin: Tutorial Handbook",
  subtitle: [Tutorial Handbook],
  tagline: [How the tool works from first principles, and how to use it: seven lessons, each with a video.],
)

#let olive-bar = rgb("#5b7d12")
#let video(name, minutes) = block(
  fill: green-tint, inset: (x: 12pt, y: 8pt), radius: 4pt, width: 100%,
  [*Watch:* #raw(name + ".mp4") (about #minutes minutes). This chapter is the same lesson in writing.],
)
#let fig(file, caption, w: 85%) = figure(image("figures/" + file, width: w), caption: caption)
#let trap(body) = block(
  inset: (left: 10pt, y: 4pt), stroke: (left: 2.5pt + olive-bar), width: 100%, body,
)
#let tryit(body) = block(
  fill: paper, stroke: 0.6pt + rule, inset: 10pt, radius: 4pt, width: 100%, [*Try it.* #body],
)

= The big idea <idea>

#video("t01-the-big-idea", 3)

Suppose a meter on a solar panel says it is making 100 watts. Is the panel healthy? You cannot tell. In full noon sun a healthy panel makes about 250 watts, so 100 watts would be a serious problem. In weak morning light (about 400 W/m²) a healthy panel makes about 98 watts, so 100 watts would be perfect. *A reading means nothing until you know what the panel should be making.*

== A model that predicts

The idea of this tool is to run a mathematical copy of the panel beside the real one, and feed both the same sunlight and the same temperature.

- The real panel is the *plant*. It produces the *measured power*.
- The copy is the *twin*. It produces the *predicted power*.

In this tool there is no real panel: the plant is simulated too, with a little sensor noise and a small deliberate mismatch from the datasheet. That lets you learn and test with no hardware.

== The deviation

The *deviation* is how far the measured power is from the predicted power, as a percentage of the prediction:

#align(center)[deviation (%) = (measured power − predicted power) ÷ predicted power × 100]

A plant making 70 W when the twin predicted 100 W has a deviation of (70 − 100) ÷ 100 × 100 = −30%. Negative means the plant makes less than it should. A plant making 104 W has +4%: positive means more than expected. What matters is the *size*; the sign says which way the plant is off.

== From a number to a state

#table(
  columns: (auto, auto, 1fr),
  [State], [Deviation (either sign)], [Meaning],
  [*Normal*], [up to 5%], [Nothing to worry about.],
  [*Warning*], [over 5%, up to 10%], [Worth a look.],
  [*Abnormal*], [over 10%], [An alarm is raised.],
)

So +4% is Normal, −7% is a Warning and −15% is Abnormal. The 5% and 10% limits are defaults; you can change them in Settings.

#trap[*Night.* At night the twin predicts almost no power and neither does the plant, so the ratio means nothing. Below 5 W of predicted power the tool shows a deviation of zero and the state stays Normal. A fault injected at night seems to do nothing: wait for the sun.]

= The twin from first principles <twin>

#video("t02-the-twin", 5)

== Light becomes current

A solar cell is a thin slice of silicon. Light knocks electrons loose, and their flow is a current. Twice the light gives twice the current, so the cell behaves like a *current source* whose size is proportional to the *irradiance* (the power of sunlight on each square metre, in W/m²). For the module in this tool, at 1000 W/m², that photocurrent is $I_"ph" = 8.9$ A.

== Where the current goes

Not all of that current reaches the wires. The silicon junction is a diode, and a diode passes almost nothing at low voltage and then conducts more and more, very quickly, as the voltage rises (an exponential). The higher the voltage across the cell, the more current the diode takes from the output. Add two imperfections of the real world: a *series resistance* $R_s$ for the metal contacts and a *shunt resistance* $R_"sh"$ for leakage paths. That circuit is the *single diode model*, and it is the whole twin:

$ I = I_"ph" - I_0 (e^((V + I R_s) / (n N_s V_t)) - 1) - (V + I R_s) / R_"sh" $

== The I-V and P-V curves

Sweep the voltage from zero up and solve the circuit at each step. The current starts at the *short-circuit current* $I_"sc" = 8.9$ A and falls to zero at the *open-circuit voltage* $V_"oc" = 37.8$ V. Power is voltage times current, so multiplying the two at every point gives a second curve with a single peak: the *maximum power point* (MPP), here about 250 W at 30.1 V and 8.3 A.

#grid(columns: (1fr, 1fr), column-gutter: 8pt,
  figure(image("figures/iv-curve.svg", width: 100%), caption: [The I-V curve, computed by the app.]),
  figure(image("figures/pv-curve.svg", width: 100%), caption: [Power against voltage: one peak.]),
)

== What the sun and the heat do

#grid(columns: (1fr, 1fr), column-gutter: 8pt,
  figure(image("figures/sun-family.svg", width: 100%), caption: [Less sun shrinks the curve in height.]),
  figure(image("figures/heat-family.svg", width: 100%), caption: [More heat shrinks it in width.]),
)

#table(
  columns: (auto, auto, auto, auto),
  [Irradiance (25 °C)], [Maximum power], [Cell temperature (1000 W/m²)], [Maximum power],
  [1000 W/m²], [249.8 W], [25 °C], [249.8 W],
  [800 W/m²], [199.9 W], [45 °C], [229.0 W],
  [500 W/m²], [123.9 W], [65 °C], [208.2 W],
  [200 W/m²], [47.6 W], [], [],
)

Power follows the sun almost in proportion, which is exactly why a lone watt reading cannot say whether a panel is healthy. Temperature acts on the other side: the datasheet's $K_i$ (+0.05 %/°C) and $K_v$ (−0.32 %/°C) say how fast the current and the voltage change with each degree.

== From datasheet to twin

The manufacturer prints seven numbers: $I_"sc"$, $V_"oc"$, $I_"mpp"$, $V_"mpp"$, $K_i$, $K_v$ and the number of cells in series $N_s$ (60). The model also needs $I_"ph"$, $R_s$ and $R_"sh"$, which are not printed, so the app finds them: it adjusts the three until the model's curve passes exactly through the datasheet points. For this module the fit gives $I_"ph" = 8.90$ A, $R_s ≈ 0.28$ Ω and $R_"sh" ≈ 11 400$ Ω (with the diode ideality factor fixed at 1.3).

Now the twin can say, for any irradiance and temperature, what a healthy module should make.

= The plant and its faults <plant>

#video("t03-plant-and-faults", 4)

== The plant is the twin's cousin

The plant uses the same model but with values of its own: series resistance 3% higher, shunt resistance 5% higher and the voltage temperature coefficient 2% off. Its sensors add noise to the irradiance and temperature readings, and voltage and current are rounded to the sensor's step. The differences are deliberate. If the plant were identical to the twin, the deviation would always be exactly zero and no test would mean anything.

#fig("day-healthy.svg", [A healthy day: in daylight the deviation never goes beyond about 2%, far inside the 5% limit.])

== Five ways to break a panel

#table(
  columns: (auto, 1fr, auto),
  [Fault], [What really happens], [Power at full sun],
  [*Partial shading*], [A shadow falls on part of the module: less light.], [174.7 W (−30%)],
  [*Soiling*], [Dust on the glass: less light, evenly.], [199.9 W (−20%)],
  [*Rs increase*], [A corroded or loose connection: loss as heat.], [148.3 W (−41%)],
  [*Diode failure*], [A bypass diode fails: a third of the cells drop out.], [160.3 W (−36%)],
  [*Sensor drift*], [The irradiance sensor reads 15% high. The panel is fine.], [249.8 W (0%)],
)

== Fingerprints

Each fault changes the curve in its own way. Shading and soiling shrink it in height, a series-resistance rise bends its knee without changing the open-circuit voltage, and a failed bypass diode makes the open-circuit voltage collapse from 37.8 V to 25.2 V. Sensor drift leaves the plant's curve exactly where it was.

#grid(columns: (1fr, 1fr), column-gutter: 6pt, row-gutter: 6pt,
  figure(image("figures/fault-partial_shading.svg", width: 100%), caption: [Partial shading.]),
  figure(image("figures/fault-soiling.svg", width: 100%), caption: [Soiling.]),
  figure(image("figures/fault-series_resistance_rise.svg", width: 100%), caption: [Series resistance rise.]),
  figure(image("figures/fault-diode_failure.svg", width: 100%), caption: [Bypass diode failure.]),
)

#trap[*The twin can be wrong too.* With sensor drift the twin trusts a sensor that reads 15% high, so it predicts more power than the healthy plant could ever make. The deviation is about −14% and the state turns Abnormal, although the panel is fine. The tool has found a disagreement, which is not always a broken panel. That is why an alarm lists a probable cause: always ask whether it is the panel or the sensor.]

== A fault on a real day

#fig("day-shading.svg", [The simulated day with partial shading injected at 11:00: the measured power falls away, the prediction does not.])
#fig("day-deviation.svg", [Underneath, the deviation jumps to about −31%, crossing the warning limit and then the abnormal limit.])

At that moment the state changes to Abnormal and an alarm is raised. Detecting a disagreement and raising an alarm is the whole purpose of the tool.

= Using the app <app>

#video("t04-using-the-app", 5)

Start the app from the applications menu or from a terminal. One window opens, with the run not yet started. The sidebar on the left has eight pages: *Dashboard*, *Analysis*, *SDM Model*, *Trends*, *Data*, *Event Log*, *Live Feed* and *Settings*. They all show the same run, so switching page never stops it.

#shot("simple_01_dashboard_idle.png", [The app when it opens: the Dashboard, with the run not started.], w: 85%)

== The controls

#shot("simple_03_toolbar.png", [Run controls and speed on the left, faults on the right. A dark button is a fault that is on.])

*Start* plays the run from the beginning, *Pause* holds it and *Reset* clears the run with its faults and alarms. The *speed* box sets how many times faster than real time the day plays (the fastest takes about three seconds for a day; 600× is comfortable for learning). The clock shows the simulated date and time of the current sample.

== The readings, the chart and the deviation card

#shot("simple_06_dashboard_fault.png", [The Dashboard with partial shading injected: the state is Abnormal and the measured power has peeled away from the prediction.], w: 90%)

Six cards show the latest voltage, current, measured power, predicted power, irradiance and module temperature. The chart plots measured power (black) against predicted power (green dashes), with a dashed vertical line where a fault was injected; the wheel zooms, a drag pans, and an *Export* button saves an image or the data.

The *deviation card* shows the deviation as the largest figure, coloured by the state, a sentence in words and the limits that decide the state. Under it are four totals: *peak power* (the highest measured power so far), *energy* (what the plant has produced, in Wh), *samples* (readings so far) and *elapsed* (simulated time since the start).

== Try it: catch a fault

#tryit[
+ Set the speed to 600× and press *Start*.
+ When the plant output has risen, click *Partial shading*.
+ Watch the deviation fall, the state turn Abnormal and the measured power peel away from the prediction.
+ Press *Clear all*; the deviation returns to Normal.
]

== Alarms and events

#shot("simple_10_event_log.png", [Event Log: the alarm with its probable cause, and the events below it.], w: 80%)

The alarms list shows each Warning or Abnormal alarm, newest first, with the time, the deviation and the probable cause. A new alarm is in bold; select it and press *Acknowledge*. Alarms stay when you press *Clear all* and are cleared only by *Reset* (or *Apply and start*). The events list records every change of state and every fault injected or removed, and *Show log* opens the application log, where the reason is when something goes wrong.

== The other pages, and comfort

*Trends* draws one chart for each of the five sensor channels. *Data* lists every sample, newest first, and *Export CSV* saves the whole run. *SDM Model* shows the twin at work: the circuit, the equations and the curves at this moment's sun and temperature. *Hide* (bottom of the sidebar) gives the page the whole window; the ☰ button, *View > Sidebar*, #key[Ctrl]+#key[B] and #key[Esc] bring the sidebar back. The *View* menu also picks System, Light or Dark colours, which the app remembers.

= Using your own data <data>

#video("t05-your-own-data", 4)

The twin needs only three things: the irradiance, the temperature and the power the panel actually made. Give it a log from a real installation (from a logger or an ESP32) and it tells you how well the panel matches the model, row by row. There are two ways in: a file, which this chapter covers, and a live feed from a device, which has its own chapter (@live).

== The file to fill in

#shot("simple_18_dataset_empty.png", [Analysis, Dataset tab: Template saves an empty file; Import file reads yours.], w: 85%)

On the Analysis page the *Dataset* tab opens first. Press *Template...* and save an empty file as Excel or CSV. Ready-made copies are in `docs/templates/`.

#table(
  columns: (auto, 1fr),
  [Column], [What to put in it],
  [`timestamp`], [Date and time of the reading, for example `2025-01-15T09:00:00`. Times must increase; the step may vary.],
  [`irradiance_w_m2`], [Irradiance on the module, in W/m². Not negative.],
  [`temperature_c`], [Module temperature, in °C.],
  [`voltage_v`, `current_a`], [Voltage and current; the app multiplies them to get the actual power.],
  [`power_w`], [Or give the actual power directly instead of voltage and current. The twin can then compare only with the module's maximum power, so give voltage and current when you can.],
)

No blanks. Delete the example rows and paste your own readings from row 2. Excel dates are understood; the old `.xls` format is not (save as `.xlsx` or CSV).

== Scoring the twin

For every row the twin predicts the power from that row's irradiance and temperature, at the voltage you measured, and compares it with the actual power. Take three rows with actual powers 80, 78 and 75 W, where the twin estimates 82, 80 and 90 W. The errors (estimated minus actual) are +2, +2 and +15 W.

#table(
  columns: (auto, auto, 1fr),
  [Figure], [Result], [How],
  [*MAE*, mean absolute error], [6.33 W], [(2 + 2 + 15) ÷ 3],
  [*RMSE*, root mean square error], [8.81 W], [√((4 + 4 + 225) ÷ 3): squaring makes the one big miss count for more],
  [*MAPE*, mean absolute percentage error], [8.35%], [(2.50% + 2.56% + 20.00%) ÷ 3],
  [*MBE*, mean bias error], [+6.33 W], [(2 + 2 + 15) ÷ 3, with the sign: positive means the twin over-predicts, so the plant is under-producing],
)

Rows where the twin predicts under 5 W are ignored in all of these, so the night never dilutes the scores.

== Reading the results

#shot("simple_19_dataset_results.png", [Dataset results for a day with shading from 11:00.], w: 90%)

The results come in three groups: the size of the dataset, the accuracy figures and the share of rows in each state. Two charts tell the same story: the deviation row by row, and estimated against actual power, where a healthy panel lies along the dashed line. This example has shading from 11:00, so the deviation drops to about −30%, the scatter splits into two lines and nearly half of the rows are Abnormal.

== Replay, export, weather and datasheets

*Replay on Dashboard* pauses the live run and sends the dataset through the whole app as if it were a run, so the Dashboard, Trends, Data and Event Log all show it; the source chip names the dataset. *Export analysis CSV* saves every analysed row and the figures. *Apply and start* in Settings brings the simulated plant back.

#shot("simple_22_settings_profile.png", [Settings, Profile: Load CSV or Excel, and the weather template.], w: 80%)

The same idea works for the weather and for the module. In *Settings*, the Profile section loads a weather file from CSV or Excel and has its own *Template...*; the Module section loads a datasheet (one parameter on each row, from Excel, CSV, JSON or TOML) and has a *Datasheet template...*. Nothing changes until you press *Apply and start*.

= Limits and trust <trust>

#video("t06-limits-and-trust", 3)

== Choosing the limits

Five and ten percent are defaults, not laws. Too tight and healthy days raise alarms; too loose and real faults slip through. *Derive from healthy run* in Settings sets the limits from a healthy simulated day: the mean deviation plus two standard deviations for the warning limit and plus three for the abnormal limit.

#fig("healthy-histogram.svg", [The size of a healthy day's deviation, with the limits Settings derives from it. The warning limit is only about 1.2%.])

On the bundled day that gives a warning limit of about 1.2%, and about 4% of healthy daylight samples would exceed it, because the healthy deviation is not a neat bell shape. Check derived limits before you trust them.

== Validation: testing the tester

*Validation* (Analysis, Simulation tab) runs one healthy day and one day for each of the five faults and scores the twin against what it knows is true.

#shot("simple_15_analysis_results.png", [Validation results: accuracy on healthy data, fault detection, a table for each fault and the table of what the twin said against what was true.], w: 75%)

On healthy data MAE is 0.24 W, RMSE 0.35 W and MAPE 0.47%. The *baseline offset*, the healthy day's average deviation, is −0.05%: the zero the faults are measured from. All five faults are detected with a delay of 0 s and there are no false alarms at the default limits, and each fault row shows its *mean deviation* (about −31% for partial shading, about −14% for sensor drift). Every healthy sample read Normal and every fault sample read Abnormal.

#trap[*Read the scores with care.* Each fault is injected as a sudden step for one hour, so the twin notices at once and the scores come out perfect. Real faults arrive gradually and would score lower. And the plant and the twin are the same kind of model, so the accuracy shows how well the twin matches the simulation, not how it would do on a real module. That is why the dataset route matters: it is how you test the twin against real measurements.]

== The whole path

The sun and the temperature set what a healthy module should make. The twin predicts it. The deviation measures the gap, and the limits turn it into a state.

#tryit[Inject each fault and read its fingerprint on the Trends page. Import a dataset made from the template. Compare the derived limits with the defaults. Then run validation and read its caveat.]

= Connecting a live feed <live>

#video("t07-live-feed", 5)

So far the readings were simulated or came from a file. The *Live Feed* takes them straight from a device, such as an ESP32 with a voltage and current sensor, as they happen. The device sends each reading over the network, as a small message, to this computer, and the app scores it the moment it arrives, exactly as it scores a row of a dataset: the twin predicts the power at the voltage the device measured and compares it with the power the module made.

#shot("simple_24_live_page.png", [The Live Feed page while readings arrive: the settings, the address and token a device needs, and the status.], w: 85%)

== Start listening

+ Open *Live Feed*. Check the *port* (8765 by default) and whether other devices on the network may send. Tick the box for an ESP32 on your Wi-Fi; leave it clear to accept readings only from this computer.
+ Press *Start listening*. The Dashboard's source chip reads *Source: live feed*, and the page shows the address to send to.
+ Give the device the address and the *token* (*Copy token*). A device must send the token with every reading, so only your devices can; *New token* makes another one.
+ Press *Stop* when you have finished. What arrived stays on the Dashboard.

== What a device sends

The device sends an HTTP POST to the address, with the token in an `X-Api-Key` header and a JSON body, one reading or a list of readings:

```
{"g": 640.0, "t": 32.5, "v": 29.0, "i": 5.2}
```

#table(
  columns: (auto, 1fr),
  [Key], [What it is],
  [`g`], [Irradiance on the module, in W/m². Required, not negative.],
  [`t`], [Module temperature, in °C. Required.],
  [`v`, `i`], [The module's voltage in V and current in A. The power is their product.],
  [`power`], [Power in W instead of `v` and `i`. The twin then compares it with the module's maximum power, so send voltage and current when you can.],
  [`timestamp`], [Optional, as `2025-01-15T10:00:00`. Without it the app stamps the reading when it arrives.],
)

The reply says what happened: *202* the readings were taken, *401* the token is missing or wrong, *422* every reading was refused (the reply says why), *400* the body is not JSON.

#tryit[You do not need the device to try it. The page shows a `curl` command with your own address and token. Copy it, paste it into a terminal and press Enter: one reading arrives, the Dashboard shows it and the status counts one accepted reading.]

== Time, gaps and silence

#shot("simple_25_live_dashboard.png", [The Dashboard on a live feed that began at 13:00: the chart starts at the first reading and the run controls are switched off.], w: 80%)

While a feed is the source, the *speed box and the run controls are switched off*: readings arrive in real time, so there is nothing to speed up, pause or inject, and the clock shows the time of the latest reading. Start sending whenever you like: a reading is scored when it arrives, so starting at midday raises nothing for a missing morning, and a gap in the middle raises nothing either.

*Silence is noticed separately.* If nothing arrives for the *No data after* time (30 s by default), the state chip turns amber and reads *No data*, and the log records it. It returns to the latest reading's state when readings resume.

#trap[*A device that stops sending is never shown as Normal.* Look at the chip, and at the last reading time on the Live Feed page.]

== Keeping the readings, and the limits

Every accepted reading is also written to a CSV file, named from the moment you start (`live-20261030-140500.csv`); import it in *Analysis* to score the whole day again. A reading is refused, with the reason on the page, if a value is missing, irradiance is negative or its time is not after the reading before it.

*Limits.* It is plain HTTP with a shared token, so anyone listening on the network can read the token and the readings. It takes one module and one feed; the history grows while it runs; `t` must be the module's temperature, not the air's; and you should check your sensors' ranges against your module. The example sketch `docs/esp32/pvysics_feed.ino` is a starting point and is untested on hardware.

The manuals (`user-manual-simple`) describe every page, button and file format in detail.
