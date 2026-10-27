// PV Digital Twin: User Manual for the advanced version (Typst source).
//
// Build from the repository root (see manual-style.typ):
//
//   typst compile --root . --font-path src/pvysics/gui/fonts docs/user-manual.typ docs/user-manual.pdf
//
// The PDF is generated and not tracked (see .gitignore).

#import "manual-style.typ": *
#show: manual.with(
  version: "0.2.0",
  doc-title: "PV Digital Twin: User Manual",
  subtitle: [User Manual],
  tagline: [Run the simulated PV plant and its digital twin, set up a run, inject faults and read the results.],
)

= What the system does <what>

This manual shows how to run the simulated PV plant and its digital twin, set up a run, inject faults and read the results. No hardware is needed: the plant is simulated.

The app runs two models side by side over a day of sunlight and temperature:

- *The plant* is a simulated PV module with sensor noise and a small mismatch from the datasheet. It stands in for the real hardware.
- *The twin* predicts the module's power from the measured irradiance and temperature, using the single diode model.

The *deviation* is how far the plant's measured power is from the twin's prediction, in percent. When it passes a limit the *state* changes:

#table(
  columns: (auto, 1fr),
  [State], [Meaning],
  [*Normal*], [Deviation is inside the warning limit.],
  [*Warning*], [Deviation has passed the warning limit.],
  [*Abnormal*], [Deviation has passed the abnormal limit. An alarm is raised.],
)

You can inject faults into the plant (shading, soiling and so on) and watch the twin catch them.

There are three windows on one run:

#table(
  columns: (auto, 1fr),
  [Window], [What it is for],
  [*HMI*], [Drive the run: start, pause, inject faults, set up the run. Shows the deviation and the twin's prediction.],
  [*Dashboard*], [Watch the comparison: charts, alarms, the event list and the validation report. Read-only.],
  [*Sensors*], [The plant's own readings, and the setup of the plant and its source. When hardware is added, it connects here.],
)

#shot("light_01_windows.png", [The three windows on one run: the HMI, the Dashboard and the Sensors window (left to right).])

= Starting the app <starting>

From the repository root:

```
uv run pvysics
```

This opens the *simple window*: one window with a sidebar of pages, in the theme you chose (*View > System*, *Light* or *Dark*).

#shot("light_20_simple_window.png", [The simple window's Dashboard, with partial shading injected: the controls and faults on top, six readings, the power chart, and the deviation with its state and the run's totals.])

#shot("dark_20_simple_window.png", [The same page in the dark theme.])

#table(
  columns: (auto, 1fr),
  [Page], [What it holds],
  [*Dashboard*], [The run controls and fault buttons, six readings, the power chart, and the deviation with its state, the limits, peak power, energy, sample count and elapsed time. *Open event log* goes to the Event Log page.],
  [*Analysis*], [Validation: the twin against one healthy day and one day for each fault. See @validation.],
  [*SDM Model*], [The circuit, equations, fitted parameters and live I-V and P-V curves. See @model.],
  [*Trends*], [A chart for each of the five sensor channels.],
  [*Data*], [Every sample of the run as a table, newest first. *Export CSV* saves the whole run.],
  [*Event Log*], [The alarms, with *Acknowledge*, the state changes and fault injections, and *Show log* for the application log.],
  [*Settings*], [The setup of the next run, described in @setting-up. *Apply and start* starts it and returns to the Dashboard.],
)

*Hide* hides the sidebar so a page has the whole window. A ☰ button stays at the top left; it, *View > Sidebar* (#key[Ctrl]+#key[B]) and #key[Esc] all bring the sidebar back.

The simple window has its own manual (`user-manual-simple.typ`). The rest of this manual describes the *advanced version*: the HMI, the Dashboard and the Sensors window, which add the Model view, validation, chart docks and the plant setup. To start it, set the environment variable `PVYSICS_ADVANCED_VERSION` to `1` (`true`, `yes` and `on` also work):

```
PVYSICS_ADVANCED_VERSION=1 uv run pvysics
```

In PowerShell, set `$env:PVYSICS_ADVANCED_VERSION = "1"` first. All three windows then open together on the same run. The switches below work only in the advanced version; the simple window takes none.

#table(
  columns: (auto, 1fr),
  [Command], [Opens],
  [`uv run pvysics` or `--all`], [the HMI, the Dashboard and the Sensors window],
  [`--hmi`], [the HMI only],
  [`--dashboard`], [the Dashboard only],
  [`--sensors`], [the Sensors window only],
  [`--both`], [the HMI and the Dashboard],
)

A closed window comes back from the *Window* menu. The app quits when the last window closes.

#shot("light_19_window_menu.png", [The Window menu opens the other windows.], w: 34%)

= The HMI <hmi>

The HMI has three tabs: *Process*, *Model* and *Setup*.

== Process <process>

This is where you run the simulation. Before a run starts the figures are empty and the chart shows a day.

#shot("light_02_process_idle.png", [The Process tab before a run: the toolbar, the empty deviation figure with its rail, and the power chart.])

#shot("light_03_process_fault.png", [The Process tab during a run with partial shading injected: the state is Abnormal, the deviation is far below the prediction and the chart shows measured power falling away from the predicted power.])

*Toolbar* (the row at the top)

#shot("light_03a_toolbar.png", [The toolbar: run controls, speed and clock on the left, fault injection on the right. The dark button is a fault that is on.])

#table(
  columns: (auto, 1fr),
  [Control], [What it does],
  [*Start*], [Plays the run from the beginning, or resumes it after a pause.],
  [*Pause*], [Holds the run where it is.],
  [*Reset*], [Clears the run so it can start again.],
  [*Speed* (`1x` to `28800x`)], [How many times faster than real time the run plays. At 28800x a whole day plays in about 3 seconds.],
  [Clock], [The simulated date and time of the current sample.],
  [*Inject a fault* buttons], [Partial shading, Soiling, Rs increase, Diode failure, Sensor drift. Click one to inject that fault into the plant. A fault that is on shows as a dark button.],
  [*Clear all*], [Removes every injected fault.],
)

*Figures*

#shot("light_03b_deviation_strip.png", [The figures: the deviation as the largest number, the state in words under it, a rail with the limits and a marker at the current deviation, and the twin's predicted power.])

#table(
  columns: (auto, 1fr),
  [Group], [Shows],
  [Deviation], [The largest figure on the screen: how far the plant is from the twin, in percent. Under it, the state in words, and a rail with the limits (zero in the middle, warning and abnormal either side) and a marker for where the deviation is now.],
  [Twin], [Predicted power from the twin],
)

The plant's measured readings (power, irradiance, module temperature, voltage and current) are in the #link(<sensors>)[Sensors window]. Alarms are on the #link(<dashboard>)[Dashboard].

*The chart* plots measured power (black) against predicted power (green, dashed). A dashed vertical line marks a fault injection. The wheel zooms and a drag pans. While the pointer is over the chart an *Export* button appears at its top right corner.

#shot("light_03c_chart_export_button.png", [The Export button, at the top right of a chart while the pointer is over it.])

#shot("light_03d_chart_export_menu.png", [The Export menu: save the chart as an image or as CSV data, or reset the view to the whole chart.], w: 22%)

== Model <model>

This tab shows what the twin is computing: the circuit of the single diode model and its equations, the parameters the twin fitted from the datasheet, the live inputs and outputs, and the I-V and P-V curves at the measured irradiance and temperature.

#shot("light_04_model.png", [The Model tab: the circuit, the equations, four groups of readings and, below them, the I-V and P-V curves.])

== Setup <hmi-setup>

Setup holds the settings for the next run: the profile, the site, the module and the limits. The simulated plant is set up in the #link(<sensors>)[Sensors window]. @setting-up describes each page.

= The Dashboard <dashboard>

Use the Dashboard to watch a run and its alarms. It changes nothing. Its tabs are *Overview*, *Alarms* and *Validation*.

== Overview <overview>

#shot("light_09_dashboard_overview.png", [The Dashboard overview: headline figures on top and a chart in each dock below.])

- *The figures at the top* show predicted power, deviation, the state and the energy produced so far.
- *Each chart is a dock.* Drag its title to rearrange it, press the small button at its top right to float it, or close it.
- The charts are power (measured against predicted), deviation, the I-V and P-V curves, and (tabbed together) energy, the deviation spread, the time in each state and the events.

The tabbed pane holds four charts. Click a tab to bring one forward.

#shot("light_10_dashboard_energy.png", [The Energy tab: cumulative energy over the run.])

#shot("light_10a_dashboard_spread.png", [The Spread tab: a histogram of the daylight power deviation.])

#shot("light_10b_dashboard_states.png", [The States tab: the time spent in Normal, Warning and Abnormal.])

#shot("light_10c_dashboard_events.png", [The Events tab: state changes and fault injections, newest first.])

If you open the Dashboard before a run, it says there is no run in progress and offers *Open HMI*.

#shot("light_13_dashboard_idle.png", [The Dashboard with no run in progress.])

== Rearranging the charts <rearranging>

Every chart dock can be moved. The small button at a dock's top right floats it into a window of its own, which you can drag anywhere, including to another monitor. Double-click the floating window's title bar to dock it again. *View > Panels* lists every chart: tick one to show it, untick it to close it.

#shot("light_10e_dashboard_floating_dock.png", [The Power chart floated out of the Dashboard into its own window.])

#shot("light_10f_dashboard_view_menu.png", [The View menu on the Dashboard: the theme, Logs and the Panels list that brings a closed chart back.], w: 28%)

== Exploring and exporting a chart <exploring>

Every chart can be explored: the mouse wheel zooms and a drag pans. While the pointer is over a chart, an *Export* button appears at its top right corner. It offers *Image (PNG)...*, *Data (CSV)...* and *Reset view*.

#shot("light_10g_dashboard_chart_hover.png", [A Dashboard chart with the Export button showing.], w: 70%)

== Alarms <alarms>

An alarm is raised when the state becomes Warning or Abnormal. The *Alarms* tab lists them newest first, with the time, the state, the deviation and the probable cause. A new alarm is in bold and tinted. Press *Acknowledge* to mark it as seen. Alarms are recorded and logged even when the Dashboard is closed.

#shot("light_10d_dashboard_alarms.png", [The Alarms tab with one new Abnormal alarm for partial shading.])

== Validation <validation>

Validation tests the twin against known answers. It runs one healthy day and one day for each of the five faults. Press *Run validation*.

#shot("light_11_validation_empty.png", [The Validation tab before it has run.])

#shot("light_12_validation_results.png", [Validation results: accuracy on healthy data, fault detection, a table for each fault and the confusion matrix.])

#table(
  columns: (auto, 1fr),
  [Result], [What it tells you],
  [*MAE, RMSE, MAPE*], [How closely the twin's power matches the healthy plant. Hover the figures for what is excluded.],
  [*Detection rate*], [The share of fault samples the twin flagged as Abnormal.],
  [*Mean delay*], [How long after injection the twin noticed.],
  [*False alarms*], [How often the healthy run was flagged, at your configured limits and at limits derived from the healthy run's own noise.],
  [*Each fault*], [Whether each of the five faults was detected, how fast, and at what rate.],
  [*Twin against truth*], [A table of what was true (rows) against what the twin said (columns). Green cells are correct.],
)

*Export samples CSV...* and *Export metrics CSV...* save the data behind the results.

= The Sensors window <sensors>

The Sensors window holds everything that comes from the plant's own sensors, apart from the twin. Today the source is the simulated plant. When hardware feeds are added, this is the window where they connect, and the figures and charts here do not change.

== Live <live>

*Live* shows the five sensor readings (irradiance, module temperature, voltage, current and measured power) and a chart for each channel. The header says where the readings come from and whether hardware is connected.

#shot("light_14_sensors_live.png", [The Sensors window, Live tab: five readings, the irradiance chart, and voltage, current and measured power below.])

Irradiance and module temperature are tabs in one pane.

#shot("light_14a_sensors_temperature.png", [The Module temperature tab, next to Irradiance in the same pane.])

== Setup: the simulated plant <sensors-plant>

The *Simulated plant* part of Setup sets how far the simulated module differs from the twin's datasheet (the *Rs*, *Rsh* and temperature-coefficient offsets: a larger mismatch makes a larger healthy deviation) and the *Sensor model*: the noise on each sensor, the step size of the voltage and current readings, and the random *Seed*. The same seed gives the same run every time. *Apply and start* starts a new run with this plant.

#shot("light_15_sensors_setup_simulated.png", [Sensors, Setup tab, with the simulated plant as the source. The plant settings are below the source.])

== Setup: the source <sensors-source>

Choose where the readings come from: the simulated plant, a serial port, an MQTT broker, or an HTTP or WebSocket address. A hardware source shows its connection settings (port and baud rate, host and topic, or an address) and the *Channels*: the field name each reading arrives under.

#shot("light_16_sensors_setup_serial.png", [A serial port as the source, with its port, baud rate and the four channel names.])

*Connect* checks the settings and names anything missing.

#shot("light_16b_sensors_missing_settings.png", [Connect names what is missing: an MQTT source with no host.])

There is no hardware driver in this version. With valid settings, Connect says so, the header shows "not available yet", and the simulated plant stays the source.

#shot("light_16a_sensors_connect_message.png", [Connect with valid serial settings: no driver yet, so the header says the feed is not available.])

= Setting up a run <setting-up>

Open the HMI's *Setup* tab. The sections are listed on the left. Click one to see its page.

Nothing changes until you press *Apply and start*. The bar along the bottom shows whether your edits differ from the current run ("Matches the current run" or "Changes not applied yet"). It also holds three buttons:

#table(
  columns: (auto, 1fr),
  [Button], [What it does],
  [*Validate setup*], [Checks every value and reports problems. It starts nothing.],
  [*Reset to defaults*], [Puts every control back to its default. It applies nothing.],
  [*Apply and start*], [Checks the setup and starts a new run from the beginning.],
)

Each number field holds only the number. Its unit is the grey label beside it.

== Profile <profile>

The profile is the day of irradiance and temperature that drives the run.

#shot("light_05a_setup_profile.png", [Setup, Profile: the bundled days, Load CSV, and the NASA POWER fetch.])

- Choose a bundled day from the list, or press *Load CSV...* for your own file (see @loading).
- *Fetch profile (NASA POWER)* downloads real data for a place and dates. Tick *Use Site location* to use the latitude and longitude from the Site page, or untick it to type your own. Choose the start and end dates, the irradiance type and the time standard, then press *Fetch*. *Preview...* shows the fetched data before you use it. Fetches are cached, so a repeat fetch works offline.

== Site <site>

Where the plant is (latitude, longitude, tilt and azimuth). It labels the run and sets the default fetch position. It does not change the physics.

#shot("light_05b_setup_site.png", [Setup, Site.])

== Module <module>

The datasheet the twin predicts with: Isc, Voc, Impp, Vmpp, the temperature coefficients Ki and Kv, and the cell count Ns. Edit any value, press *Load datasheet...* to read a file, or press *Reset to generic module* to return to the generic 60-cell 250 W module.

#shot("light_05c_setup_module.png", [Setup, Module.])

== Limits <limits>

The warning and abnormal limits, in percent. *Derive from healthy run* sets them from a healthy simulated day: the mean deviation plus two and three standard deviations.

#shot("light_05d_setup_limits.png", [Setup, Limits.])

== Review <review>

A summary of what the next run will use. Check it, then press *Apply and start*.

#shot("light_05e_setup_review.png", [Setup, Review: what the next run will use.])

= Loading your own data <loading>

Press *Load CSV...* on the Profile page and choose a file. The file needs a header row, a timestamp column, an irradiance column (W/m²) and a temperature column (°C).

#shot("light_07_csv_dialog.png", [The CSV dialog: the column choices, the first rows of the file and the result of the checks.], w: 62%)

+ The dialog guesses each column from its name. Change a choice if it is wrong. NASA POWER files with `YEAR, MO, DY, HR` columns are recognised.
+ The *first rows* table shows what the file holds.
+ The check line gives the number of rows, the date range and the time step, or says *Rejected* with the reason.
+ *Use profile* is enabled only when the file passes. Press it, then *Apply and start*. *Cancel* keeps the previous profile.

A file is rejected if its times do not increase by one fixed step, any value is missing or not a number, or irradiance is negative.

When you fetch from NASA POWER, *Preview...* opens the fetched profile for inspection before it is used.

#shot("light_08_fetch_preview.png", [The fetch preview: the fetched irradiance and temperature, with statistics and checks, before you use or discard it.], w: 80%)

= Themes and the log <themes>

*Themes.* The app follows your system's light or dark setting. In the *View* menu, choose *System*, *Light* or *Dark* to override it. The look is flat: no boxes, only type, space and thin rules.

#shot("light_18_view_menu_hmi.png", [The View menu on the HMI: the theme choices and Logs.], w: 28%)

#shot("dark_02_process_idle.png", [The same Process tab in the dark theme.])

*The log.* Open it from *View > Logs* (#key[Ctrl]+#key[L]). It is a pop-up window, so it takes no room until you ask for it; close it with its close button. It lists what the app is doing as time, level and message.

#shot("light_17_log_popup.png", [The log pop-up: a fault injected, an Abnormal alarm in red, and the state change.], w: 70%)

- *Level* filters by Debug, Info, Warning or Error. Warnings are amber and errors are red.
- *Clear* empties it, and *Copy* puts the visible lines on the clipboard.

Every window has its own pop-up, and all of them show the same log.

= Quick recipes <recipes>

#recipe[Watch a fault being caught]

+ Run `uv run pvysics`.
+ In the HMI, set the speed to `600x` and press *Start*.
+ Once the plant output has risen, click *Partial shading*.
+ Watch the deviation figure and rail and the state. The Dashboard shows the same event, and the Alarms tab lists the alarm.

#recipe[Run on real weather]

+ Setup > Site: enter the plant's latitude and longitude.
+ Setup > Profile: pick dates, press *Fetch*, press *Preview...*, then *Use*.
+ Press *Apply and start*.

#recipe[Check the twin's accuracy]

+ Open the Dashboard and go to *Validation*.
+ Press *Run validation* and read the figures and tables.
+ Use *Export metrics CSV...* to keep the numbers.

#recipe[Try a noisier plant]

+ In the Sensors window, open *Setup*.
+ Raise the *Irradiance noise* or the *Rs offset*.
+ Press *Apply and start* and watch the deviation on the HMI.

#recipe[Start over]

HMI Setup > *Reset to defaults*, then *Apply and start*. For the plant, use *Reset to defaults* in the Sensors window's Setup.

= Troubleshooting <troubleshooting>

#table(
  columns: (1fr, 1.6fr),
  [Problem], [What to do],
  [The Dashboard says "No run in progress".], [Press *Open HMI* and start a run there.],
  [A CSV is rejected.], [Read the reason in the dialog. Check that the columns are mapped right and the times step evenly with no gaps.],
  [A fetch fails.], [NASA POWER needs an internet connection. The log has the reason. A date range you fetched before still loads from the cache.],
  [The state stays Normal after injecting a fault.], [At night there is too little light to compare, so no state is shown. Run on until the sun is up.],
  [Changes on Setup have no effect.], [Press *Apply and start*. Edits apply only then.],
  [The log is not showing.], [It is a pop-up: *View > Logs* (#key[Ctrl]+#key[L]). On the Dashboard, a closed chart comes back from *View > Panels*.],
  [Connect says there is no hardware driver.], [Hardware feeds are not available in this version. The simulated plant stays the source.],
)
