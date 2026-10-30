// PV Digital Twin: User Manual for the simple version, which is what the app opens by default (Typst source).
//
// Build from the repository root (see manual-style.typ):
//
//   typst compile --root . --font-path src/pvysics/gui/fonts docs/user-manual-simple.typ docs/user-manual-simple.pdf
//
// The PDF is generated and not tracked (see .gitignore). The advanced version has its own manual, user-manual.typ.

#import "manual-style.typ": *
#show: manual.with(
  version: "0.3.0",
  doc-title: "PV Digital Twin: User Manual (Simple Version)",
  subtitle: [User Manual: Simple Version],
  tagline: [Run the simulated PV plant and its digital twin from one window: start a run, inject faults and read the results.],
)

= What the app does <what>

The app compares a simulated PV module with a model of it, and tells you when they disagree. No hardware is needed: the plant is simulated.

- *The plant* is a simulated PV module with sensor noise and a small mismatch from the datasheet. It stands in for the real hardware.
- *The twin* is the Single Diode Model (SDM) of the module. It predicts the module's power from the plant's measured irradiance and temperature.
- *A run* plays a day of sunlight and temperature through both, one sample a minute of simulated time.

The *deviation* is how far the plant's measured power is from the twin's prediction, as a percentage of the prediction:

#align(center)[deviation (%) = (measured power − predicted power) ÷ predicted power × 100]

A negative deviation means the plant is producing less than the twin expects. The *state* depends on the size of the deviation, whichever way it points:

#table(
  columns: (auto, 1fr),
  [State], [Meaning],
  [*Normal*], [The deviation is inside the warning limit (5% by default).],
  [*Warning*], [The deviation has passed the warning limit.],
  [*Abnormal*], [The deviation has passed the abnormal limit (10% by default). An alarm is raised.],
)

You can inject faults into the plant (shading, soiling and so on) and watch the twin catch them. The limits are set on the Settings page (@limits).

At night the twin predicts almost no power, so there is nothing to compare: below 5 W of predicted power the deviation reads 0 and the state stays Normal.

== How the prediction is made <prediction>

*The twin.* The Single Diode Model describes the module as a current source, one diode, a series resistance $R_s$ and a shunt resistance $R_(s h)$:

#align(center)[$I = I_(p h) - I_0 (e^((V + I R_s) / (n N_s V_t)) - 1) - (V + I R_s) / R_(s h)$]

The model is fitted to the module's datasheet: the short-circuit current, the open-circuit voltage and the maximum power point decide $I_(p h)$, $I_0$, $R_s$ and $R_(s h)$. The diode ideality factor $n$ is *fixed at 1.3*, a common value for silicon modules; it is not fitted and it is not a setting. Irradiance scales the photocurrent, and the datasheet's temperature coefficients shift the current and the open-circuit voltage with temperature. The *SDM Model* page shows the fitted values and the curves.

*Which operating point is compared.* A module makes different power at different voltages, so the twin and the plant must be compared at the same point on the curve:

#table(
  columns: (auto, 1fr),
  [Where], [What is compared],
  [A simulated run], [The plant is read *at its own maximum power point*, as if a perfect maximum-power-point tracker held it there, and the twin predicts the *maximum power* for the same light and temperature. This is an *ideal-tracker assumption*: the app has no load and no tracker model, so a real module held away from its maximum power point would not be comparable in this mode.],
  [A dataset with voltage and current], [The twin predicts the power *at the measured voltage*: the voltage times the current the model gives at that voltage, for the row's irradiance and temperature. A healthy module held off its maximum power point by its load therefore still scores Normal. The module's maximum power for the row is kept beside it as a reference.],
  [A dataset with power only], [There is no voltage to predict at, so the twin predicts the maximum power, which assumes the module is being tracked. Include voltage and current when you can.],
)

*The plant's differences from the model.* So that the twin is not simply a copy of the plant, the simulated plant differs from the datasheet by default: its series resistance is 3% higher, its shunt resistance 5% higher and its open-circuit-voltage temperature coefficient 2% higher, and its sensors have noise (irradiance 0.5%, temperature 0.5 °C). On a healthy day this leaves a small steady offset between measured and predicted power, the *baseline offset*. On the default setup it is a few hundredths of a percent; the *Baseline offset* figure in Analysis shows it for your setup (@simulation-analysis).

*The limits.* The defaults of 5% (Warning) and 10% (Abnormal) are round starting values. Settings can instead work the limits out from a healthy day of the plant itself: the warning limit is the mean plus two standard deviations of the healthy deviation, and the abnormal limit the mean plus three, so the limits sit close to the plant's own noise. They are tight and flag some healthy samples, so check them before you rely on them (@limits).

= Installing and starting <starting>

*Windows.* Run `pvysics-0.3.0-windows-setup.exe` and follow the steps. It adds *PV Digital Twin* to the Start menu, and to the desktop if you tick the box. The installer is not code-signed, so Windows may show a warning: choose *More info*, then *Run anyway*. Without the installer, unzip `pvysics-0.3.0-windows.zip` and run `pvysics.exe` in the `pvysics` folder.

*Linux.* On Debian, Ubuntu and Mint, install the package and start *PV Digital Twin* from the applications menu:

```
sudo apt install ./pvysics_0.3.0_amd64.deb
```

On other distributions, unpack `pvysics-0.3.0-linux-x86_64.tar.gz` and run `./install.sh`.

*From the source code.* From the repository root:

```
uv run pvysics
```

Nothing else needs to be installed on a computer with the installer or the package: Python and Qt are inside the app. The app opens one window on a new run that has not started.

#shot("simple_01_dashboard_idle.png", [The app when it opens: the Dashboard, with the run not started.])

= The window <window>

The window has a *sidebar* of pages on the left and the page you chose on the right.

#table(
  columns: (auto, 1fr),
  [Page], [What it is for],
  [*Dashboard*], [Run the simulation, inject faults and watch the deviation. It opens first. See @dashboard.],
  [*Analysis*], [Score the twin on your own measurements, or against known answers. See @analysis.],
  [*SDM Model*], [See what the twin is computing. See @model.],
  [*Trends*], [Chart each sensor channel. See @trends.],
  [*Data*], [List every sample and save them as a CSV file. See @data.],
  [*Event Log*], [Alarms, state changes and injected faults. See @event-log.],
  [*Settings*], [Set up the next run. See @settings.],
)

All the pages show the same run. Switching page never stops it.

== Hiding the sidebar <hiding>

The *Hide* button at the bottom of the sidebar hides it, so the page has the whole window. A ☰ button stays at the top left. The sidebar comes back when you press that button, choose *View > Sidebar* or press #key[Ctrl]+#key[B] or #key[Esc].

#shot("simple_12_sidebar_hidden.png", [The sidebar hidden: the page fills the window and the ☰ button at the top left brings the sidebar back.])

== The View menu <view-menu>

#shot("simple_13_view_menu.png", [The View menu.], w: 20%)

- *System*, *Light* and *Dark* set the colours. System follows your computer's light or dark setting. The app remembers your choice.
- *Sidebar* (#key[Ctrl]+#key[B]) shows or hides the sidebar.
- *Logs* (#key[Ctrl]+#key[L]) opens the log. See @log.

#shot("simple_17_dashboard_dark.png", [The Dashboard in the dark theme.])

= The Dashboard <dashboard>

The Dashboard is where you run the simulation.

#shot("simple_06_dashboard_fault.png", [The Dashboard during a run with partial shading injected: the state is Abnormal, the deviation is far below the prediction and the chart shows measured power falling away from the predicted power.])

At the top right, the *source* chip says where the readings come from (today always the simulated plant) and the *system state* chip shows the state of the latest sample: *Waiting* before a run, then Normal, Warning or Abnormal.

== The controls <controls>

#shot("simple_03_toolbar.png", [The controls: run controls, speed and clock on the left, fault injection on the right. The dark button is a fault that is on.])

#table(
  columns: (auto, 1fr),
  [Control], [What it does],
  [*Start*], [Plays the run from the beginning, or resumes it after a pause.],
  [*Pause*], [Holds the run where it is.],
  [*Reset*], [Clears the run, its faults and its alarms, so it can start again.],
  [*Speed* (`1x` to `28800x`)], [How many times faster than real time the run plays. At 28800x a whole day plays in about 3 seconds.],
  [Clock], [The simulated date and time of the current sample.],
  [*Inject a fault* buttons], [Inject that fault into the plant. A fault that is on shows as a dark button. See @faults.],
  [*Clear all*], [Removes every injected fault.],
)

The run stops by itself at the end of the day. Press *Reset*, then *Start*, to play it again.

== The readings <readings>

#shot("simple_04_readings.png", [The six readings of the latest sample.])

The plant's own sensors give the voltage, current, *measured power*, irradiance and module temperature. The twin gives the *predicted power*. Before a run each reading shows dashes.

== The chart <chart>

The chart plots measured power against predicted power. A dashed vertical line marks a fault injection. The mouse wheel zooms and a drag pans. While the pointer is over the chart an *Export* button appears at its top right corner, with *Image (PNG)...*, *Data (CSV)...* and *Reset view*. *Save chart* above the chart saves it as an image.

== The deviation card <deviation-card>

#shot("simple_07_deviation_card_fault.png", [The deviation card with a fault on.], w: 38%)

The card shows the deviation as the largest figure, coloured by the state. Under it are a sentence in words ("31.3% below the prediction") and the limits that decide the state. Four totals for the run follow:

#table(
  columns: (auto, 1fr),
  [Total], [What it is],
  [*Peak power*], [The highest measured power so far, in watts.],
  [*Energy*], [The energy the plant has produced so far, in watt-hours.],
  [*Samples*], [How many samples the run has produced.],
  [*Elapsed*], [How much simulated time has passed since the start of the run.],
)

*Open event log* goes to the Event Log page.

== Faults <faults>

A fault changes the plant, so its power drifts away from what the twin predicts. Sensor drift is different: the plant is fine and the twin is wrong.

#table(
  columns: (auto, 1fr),
  [Fault], [What it models],
  [*Partial shading*], [Part of the module is shaded: less photocurrent, so less power.],
  [*Soiling*], [Dust on the glass: less light reaches the cells.],
  [*Rs increase*], [A degraded connection: more series resistance, so more loss.],
  [*Diode failure*], [A bypass diode has failed: a group of cells drops out.],
  [*Sensor drift*], [The irradiance sensor reads high: the twin predicts wrongly, the plant is fine.],
)

Each fault is injected at a fixed strength. Several faults can be on at once, and a fault stays on until you press *Clear all* or *Reset*.

= Analysis <analysis>

Analysis tests the twin in two ways. The two buttons at the top right of the page switch between them.

- *Dataset* (the one that opens) scores the twin on measurements you import. It needs no plant and no hardware.
- *Simulation* scores the twin against a plant the app simulates. See @simulation-analysis.

== Dataset analysis <dataset-analysis>

A dataset is a CSV or Excel file of the plant's own readings, such as a logger or an ESP32 would write. The twin predicts the power from each row's irradiance and temperature, at the row's measured voltage when the file has one (see @prediction), and the page compares that with the power the plant actually made.

#shot("simple_18_dataset_empty.png", [Dataset analysis before a file is imported.])

#table(
  columns: (auto, 1fr),
  [Button], [What it does],
  [*Template...*], [Saves an empty file with the right columns and a few example rows, as Excel (`.xlsx`) or CSV. See @dataset-file.],
  [*Import file...*], [Reads a CSV or Excel file into the app's dataset list and chooses it. The file is copied, so the original can be moved or deleted.],
  [*Analyse*], [Scores the chosen dataset with the twin, using the datasheet and limits in Settings. It runs in the background.],
  [*Replay on Dashboard*], [Shows the analysed dataset on every page as if it were a run. See below.],
  [*Export analysis CSV*], [Saves every analysed row, then the figures below, as one CSV file. Each row has the estimated power and, in `mpp_power_w`, the module's theoretical maximum power for that row's light and temperature.],
  [*Delete dataset*], [Removes the chosen dataset from the list.],
)

The *Dataset* list holds every dataset you have imported, and keeps them between sessions.

=== The file and its template <dataset-file>

*Start from the template.* Press *Template...*, choose *Excel workbook* or *CSV file*, and save it. Copies are also in the `docs/templates` folder of the source code (`pvysics-dataset-template.xlsx` and `pvysics-dataset-template.csv`). The Excel template has two sheets: *Measurements*, with the columns and five example rows of a healthy generic 250 W module, and *Instructions*, with a line about each column. Delete the example rows and paste your own readings from row 2, keeping the column names in row 1.

The file is a `.csv` or an `.xlsx`. For an Excel file, the first sheet is read, and a time that Excel has turned into a date is understood. An older `.xls` file must be saved again as `.xlsx` or CSV.

The file needs a header row and one row for each reading. The columns are found by name, in any case. The names in the template are the first choice for each:

#table(
  columns: (auto, 1fr),
  [What], [Header names that are recognised],
  [Time], [`timestamp`, `time`, `datetime` or `date`, as a date and time such as `2025-01-15T10:00:00`],
  [Irradiance (W/m²)], [`G`, `ghi`, `irradiance`, `irradiance_w_m2` or `ghi_w_m2`],
  [Module temperature (°C)], [`T`, `temperature`, `temp`, `temp_air`, `module_temperature` or `pv_temp`],
  [Power (W)], [`power`, `power_w`, `actual_power` or `pv_power`, *or* both of the next two],
  [Voltage (V) and current (A)], [`voltage` or `pv_voltage`, and `current` or `pv_current`. The power is their product],
)

The times must increase, but the step may vary, because real logs have gaps. A file is rejected, with the reason shown, if a column is missing, a value is missing or not a number, irradiance is negative or there are fewer than two rows.

=== Filling the file in properly <dataset-fill>

The twin can only judge readings that were taken in the way it expects. Before you import, check these points:

+ *Use the same module.* The prediction comes from the datasheet in Settings (*Module*). Load the datasheet of the module you measured before you press *Analyse*, or the comparison is between two different modules.
+ *Irradiance* is the sunlight on the module's own surface, in W/m², from a sensor tilted like the module (a plane-of-array or reference-cell sensor). A horizontal reading differs from it, especially in the morning and evening.
+ *Temperature* is the module's temperature in °C, from a sensor on the back of the module. The air temperature is lower than the module's in sunshine, so it makes the twin predict too much power. If you only have air temperature, expect the twin to read high.
+ *Voltage and current* are the module's own terminals, in V and A, read at the same moment as the irradiance. Every row is one moment, so the readings should be averages over the row's interval, not a single noisy value.
+ *Include voltage and current.* With them, the twin predicts the power at the voltage you measured, so it does not matter whether the module was held at its maximum power point or at a load. A file with only a power column is compared with the module's *maximum* power, which assumes a tracker held it there, so a module on a fixed load will read low.
+ *Check the numbers make sense for the module.* The current can never be above the datasheet's short-circuit current (*Isc*), the voltage above its open-circuit voltage (*Voc*), or the power above the datasheet's rated power in full sunshine. A row beyond these usually means a unit error (kW instead of W, mA instead of A), a swapped column, or a sensor out of calibration, and it will score as Abnormal.
+ *Keep the rows in order and the step steady,* with no gaps you do not mean. A few missing rows are fine, but a missing value is rejected, so delete the row or fill it.

A good first test is the template itself: it holds a healthy generic module, so with the default limits it scores *Normal* on every row. Import it, press *Analyse*, and you will see what a healthy result looks like before you try your own file.

*Reading the result.* A deviation within the Normal limit (5% by default) means the module makes the power the twin expects. Between the limits is *Warning*, and above the abnormal limit (10% by default) is *Abnormal*. A steady offset on every row points at the setup (the wrong datasheet, the wrong temperature, a miscalibrated sensor), while a deviation that appears at certain hours or after a certain time points at the plant, such as shading, soiling or a failing string.

=== The results <dataset-results>

#shot("simple_19_dataset_results.png", [Dataset results: the figures, the deviation along the dataset and estimated power against actual power. This dataset has shading from 11:00.])

#table(
  columns: (auto, 1fr),
  [Figure], [What it tells you],
  [*Samples*, *Mean G*, *Mean actual P*, *Mean estimated P*], [The size of the dataset and its averages. The estimated power is the twin's, at the measured voltage when the file has one.],
  [*MAE*, *RMSE*, *MAPE*], [How far the twin's power is from the actual power, in watts and in percent.],
  [*MBE*], [The mean of estimated minus actual power. Positive means the twin over-predicts, so the plant is under-producing.],
  [*Mean deviation*], [The average deviation in percent, with the sign explained in @what.],
  [*Normal*, *Warning*, *Abnormal*], [The share of the rows in each state, using the limits in Settings.],
)

The figures use daylight rows only, where the twin predicts at least 5 W, so night rows do not dilute them. MAPE also skips rows where the actual power is under 5 W. Two charts show the deviation row by row and the estimated power against the actual power: a healthy plant lies along the dashed line.

=== Replaying a dataset <dataset-replay>

*Replay on Dashboard* pauses the live run and puts the dataset's rows through the app as the run. The Dashboard, Trends, Data and Event Log then show the dataset, and the source chip on the Dashboard reads *Source: dataset* and its name. A dataset has no injected faults, so only its state changes are listed. Pressing *Apply and start* in Settings starts a simulated run again, and the chip goes back to the simulated plant.

#shot("simple_21_dashboard_replay.png", [The Dashboard after a replay: the source chip names the dataset, and the chart shows the actual power falling away from the twin's prediction where the dataset has shading.])

#recipe[Score your own measurements]

+ Open *Analysis*, make sure *Dataset* is chosen, and press *Template...* if you need the file to fill in.
+ Press *Import file...* and choose your file, then press *Analyse* and read the figures.
+ Press *Replay on Dashboard* to see the rows against the twin's prediction, and *Export analysis CSV* to keep the numbers.

== Simulation analysis <simulation-analysis>

The *Simulation* button shows the validation of the twin against known answers. It runs one healthy day and one day for each of the five faults, with the setup you last applied. Press *Run validation*; it takes a few seconds and the app stays usable while it runs.

#shot("simple_14_analysis_empty.png", [Analysis before it has run.])

#shot("simple_15_analysis_results.png", [Analysis results: accuracy on healthy data, fault detection, a table for each fault and the table of what the twin said against what was true.])

#table(
  columns: (auto, 1fr),
  [Result], [What it tells you],
  [*MAE, RMSE, MAPE*], [How closely the twin's power matches the healthy plant, in watts and in percent. Hover the figures for what is excluded.],
  [*Baseline offset*], [The healthy day's mean deviation, with its sign. It comes from the plant's small differences from the datasheet (@prediction) and is the zero the faults are measured from.],
  [*Detection rate*], [The share of fault samples the twin flagged as Abnormal.],
  [*Mean delay*], [How long after injection the twin noticed.],
  [*False alarms*], [How often the healthy day was flagged, at your limits and at limits worked out from the healthy day's own noise.],
  [*Each fault*], [Whether each of the five faults was detected, how fast, at what rate, and its *mean deviation*: how far below the prediction the plant sat while the fault was on, in percent.],
  [*Twin against truth*], [A table of what was true (rows) against what the twin said (columns). Green cells are correct.],
)

*Export samples CSV...* and *Export metrics CSV...* save the data behind the results. After you change the setup, the old result is marked out of date until you run validation again.

#block(inset: (left: 10pt), stroke: (left: 2.5pt + sun), [
  *Read the results with care.* Each fault is injected as a sudden step at 10:00 for one hour, so the twin notices at once and the scores are perfect. Real faults arrive gradually and would score lower. The plant and the twin are the same kind of model, so the accuracy figures show how well the twin matches the simulated plant, not how it would do on a real module.
])

= SDM Model <model>

This page shows what the twin is computing: the circuit of the Single Diode Model and its equations, the parameters the twin fitted from the datasheet, the live inputs and outputs, and the I-V and P-V curves at the measured irradiance and temperature. The page scrolls when the window is small.

#shot("simple_11_model.png", [The SDM Model page: the circuit, the equations and the groups of readings above the I-V and P-V curves.])

= Trends <trends>

Trends draws one chart for each sensor channel over the run: irradiance, module temperature, voltage, current and measured power. They are the same readings as the Dashboard's, as charts.

#shot("simple_08_trends.png", [The Trends page.])

Every chart can be explored in the same way as the Dashboard chart: the wheel zooms, a drag pans, and the *Export* button saves an image or the data.

= Data <data>

Data lists every sample of the run, newest first: the time, the plant's readings, the twin's prediction, the deviation, the state and any faults that were on.

#shot("simple_09_data.png", [The Data page.])

The table shows the newest 1000 samples. *Export CSV* saves every sample of the run, not only the rows shown, as a CSV file that opens in a spreadsheet.

= Event Log <event-log>

#shot("simple_10_event_log.png", [The Event Log page: one new Abnormal alarm and the events that led to it.])

*Alarms.* An alarm is raised when the state becomes Warning or Abnormal. The list shows the newest first, with the time, the state, the deviation and the probable cause. A new alarm is in bold and tinted. Select it and press *Acknowledge* to mark it as seen. Alarms are kept when you press *Clear all*; *Reset* or *Apply and start* clears them.

*Events.* Every change of state and every fault injected or removed, newest first.

== The log <log>

*Show log* (or *View > Logs*, #key[Ctrl]+#key[L]) opens the application log in a pop-up window. It lists what the app is doing as time, level and message.

#shot("light_17_log_popup.png", [The log pop-up: a fault injected, an Abnormal alarm in red, and the state change.], w: 70%)

- *Level* filters by Debug, Info, Warning or Error. Warnings are amber and errors are red.
- *Clear* empties it, and *Copy* puts the visible lines on the clipboard.

If something goes wrong, the log has the reason.

= Settings <settings>

Settings holds the setup of the *next* run: the profile, the site, the module and the limits. The sections are listed on the left. Click one to see its page.

#shot("simple_16_settings.png", [Settings, with the Profile section open.])

Nothing changes until you press *Apply and start*. The bar along the bottom shows whether your edits differ from the current run ("Matches the current run" or "Changes not applied yet"). It also holds three buttons:

#table(
  columns: (auto, 1fr),
  [Button], [What it does],
  [*Validate setup*], [Checks every value and reports problems. It starts nothing.],
  [*Reset to defaults*], [Puts every control back to its default. It applies nothing.],
  [*Apply and start*], [Checks the setup, starts a new run from the beginning and returns to the Dashboard.],
)

Each number field holds only the number. Its unit is the grey label beside it.

== Profile <profile>

The profile is the day of irradiance and temperature that drives the run.

#shot("simple_22_settings_profile.png", [Settings, Profile: the bundled days, Load CSV or Excel, the weather template, and the NASA POWER fetch.])

- Choose a bundled day from the list, or press *Load CSV or Excel...* for your own file. *Template...* saves an empty weather file to fill in (see @loading).
- *Fetch profile (NASA POWER)* downloads real weather for a place and dates. Tick *Use Site location* to use the latitude and longitude from the Site section, or untick it to type your own. Choose the start and end dates, the irradiance type and the time standard, then press *Fetch*. A request covers at most 31 days, and the end date cannot be in the future. *Preview...* shows the fetched data before you use it. Fetches are kept, so a repeat fetch works without a connection.

== Site <site>

Where the plant is (latitude, longitude, tilt and azimuth). It labels the run and sets the default fetch position. It does not change the physics.

#shot("light_05b_setup_site.png", [Settings, Site.])

== Module <module>

The datasheet the twin predicts with: Isc, Voc, Impp, Vmpp, the temperature coefficients Ki and Kv, and the cell count Ns. Edit any value, press *Load datasheet...* to read a file (Excel, CSV, JSON or TOML), press *Datasheet template...* to save an empty one to fill in, or press *Reset to generic module* to return to the generic 60-cell 250 W module. See @datasheet-file for the file.

#shot("simple_23_settings_module.png", [Settings, Module: the datasheet values and the buttons to load a file, save the template or return to the generic module.])

=== The datasheet file <datasheet-file>

The easiest start is the template: press *Datasheet template...*, choose *Excel workbook* or *CSV file*, and save it. Copies are in the `docs/templates` folder of the source code (`pvysics-datasheet-template.xlsx` and `.csv`). Replace the example values with those on your module's datasheet, which are at standard test conditions (1000 W/m² and 25 °C).

The file has one parameter on each row, with its name in the first column and its value in the second. The unit and notes columns are for you and are not read. Names are found in any case, and a unit in brackets (`Isc (A)`) is ignored.

#table(
  columns: (auto, auto, 1fr),
  [Parameter], [Unit], [What it is],
  [`name`], [text], [A label for the module. Left out, it is the file's name.],
  [`Isc`], [A], [Short-circuit current.],
  [`Voc`], [V], [Open-circuit voltage.],
  [`Impp`], [A], [Current at maximum power. Must be below Isc.],
  [`Vmpp`], [V], [Voltage at maximum power. Must be below Voc.],
  [`Ki`], [%/°C], [Temperature coefficient of Isc.],
  [`Kv`], [%/°C], [Temperature coefficient of Voc, which is negative.],
  [`Ns`], [cells], [Cells in series, a whole number.],
  [`Pmpp`], [W], [Optional rated power. Without it the app uses Vmpp times Impp.],
)

A file with a row missing, a value that is not a number or a value that does not describe a module that can be modelled is rejected with the reason, and the module stays as it was. JSON and TOML datasheets still work.

== Limits <limits>

The warning and abnormal limits, in percent of deviation. The defaults are 5% and 10%. *Derive from healthy run* sets them from a healthy simulated day: the mean deviation plus two and three standard deviations. Those limits are tight, and on the bundled day they flag some healthy samples, so check them before you rely on them.

#shot("light_05d_setup_limits.png", [Settings, Limits.])

== Review <review>

A summary of what the next run will use. Check it, then press *Apply and start*.

#shot("light_05e_setup_review.png", [Settings, Review: what the next run will use.])

= Loading your own data <loading>

Press *Load CSV or Excel...* on the Profile section and choose a file. To start from a file that is known to work, press *Template...* first, choose *Excel workbook* or *CSV file*, and save it; copies are in the `docs/templates` folder (`pvysics-weather-template.xlsx` and `.csv`). The template holds one example day, hourly. Delete its rows and paste your own readings from row 2.

The file is a `.csv` or an `.xlsx` (the first sheet is read, and a time that Excel has turned into a date is understood). It needs a header row, a timestamp column, an irradiance column (W/m²) and a temperature column (°C).

#shot("light_07_csv_dialog.png", [The CSV dialog: the column choices, the first rows of the file and the result of the checks.], w: 62%)

+ The dialog guesses each column from its name. Change a choice if it is wrong. NASA POWER files with `YEAR, MO, DY, HR` columns are recognised.
+ The *first rows* table shows what the file holds.
+ The check line gives the number of rows, the date range and the time step, or says *Rejected* with the reason.
+ *Use profile* is enabled only when the file passes. Press it, then *Apply and start*. *Cancel* keeps the previous profile.

A file is rejected if its times do not increase by one fixed step, any value is missing or not a number, or irradiance is negative.

When you fetch from NASA POWER, *Preview...* opens the fetched profile for inspection before it is used.

#shot("light_08_fetch_preview.png", [The fetch preview: the fetched irradiance and temperature, with statistics and checks, before you use or discard it.], w: 80%)

= Quick recipes <recipes>

#recipe[Watch a fault being caught]

+ Open the app. On the Dashboard, set the speed to `600x` and press *Start*.
+ Once the plant output has risen, click *Partial shading*.
+ Watch the deviation, the state and the chart. Open *Event Log* to see the alarm.

#recipe[Run on real weather]

+ Settings > Site: enter the plant's latitude and longitude.
+ Settings > Profile: pick dates, press *Fetch*, press *Preview...*, then *Use*.
+ Press *Apply and start*.

#recipe[Check the twin's accuracy]

+ Open *Analysis* and press *Simulation*.
+ Press *Run validation* and read the figures and tables.
+ Use *Export metrics CSV...* to keep the numbers.

#recipe[Keep the data of a run]

+ Play the run to the end, or as far as you need.
+ Open *Data* and press *Export CSV*.

#recipe[Start over]

Press *Reset* on the Dashboard to play the same run again. For different settings, open *Settings*, press *Reset to defaults*, then *Apply and start*.

= Troubleshooting <troubleshooting>

#table(
  columns: (1fr, 1.6fr),
  [Problem], [What to do],
  [The sidebar has gone.], [Press the ☰ button at the top left, or #key[Ctrl]+#key[B], or #key[Esc].],
  [Nothing moves.], [The run has not started or is paused. Press *Start* on the Dashboard.],
  [The state stays Normal after injecting a fault.], [At night there is too little light to compare, so the deviation reads 0. Run on until the sun is up.],
  [Changes in Settings have no effect.], [Press *Apply and start*. Edits apply only then.],
  [A CSV is rejected.], [Read the reason in the dialog. Check that the columns are mapped right and the times step evenly with no gaps.],
  [A fetch fails.], [NASA POWER needs an internet connection. The log has the reason. A date range you fetched before still loads without a connection.],
  [A dataset is rejected.], [Read the reason on the Analysis page. Check that the header names are ones the manual lists, that the times increase and that no value is missing.],
  [A dataset scores Abnormal on every row.], [A steady offset is a setup problem, not a fault. Check that the Settings datasheet is the module you measured, that the temperature is the module's and not the air's, that the units are W/m², °C, V and A, and that no row has a current above the datasheet's short-circuit current. A file with only a power column is compared with the maximum power, so a module held at a load reads low; add voltage and current. See @dataset-fill.],
  [Analysis says the result is out of date.], [You changed the setup after the last validation. Press *Run validation* again.],
  [The log is not showing.], [It is a pop-up: *View > Logs* (#key[Ctrl]+#key[L]).],
  [The app opens three windows, not one.], [The advanced version is switched on. Unset the environment variable `PVYSICS_ADVANCED_VERSION`.],
)

= The advanced version <advanced>

The advanced version is the app as it was before the simple window: separate windows for the operator (the HMI), the Dashboard and the Sensors. It adds charts you can rearrange and float onto other monitors, and setup of the simulated plant's noise, mismatch and seed. To start it, set the environment variable `PVYSICS_ADVANCED_VERSION` to `1` (`true`, `yes` and `on` also work) before you start the app:

```
PVYSICS_ADVANCED_VERSION=1 uv run pvysics
```

On Windows, in PowerShell, set it for the session first: `$env:PVYSICS_ADVANCED_VERSION = "1"`, then run `.\pvysics.exe` from the app's folder. The advanced version has its own manual.
