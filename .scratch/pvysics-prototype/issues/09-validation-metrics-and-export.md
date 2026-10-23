# 09: Validation metrics, fault-detection scoring and export

**What to build:** the Dashboard's Validation tab. For a healthy run it shows MAE, RMSE and MAPE between P measured and P predicted. For a set of labelled fault runs it shows a confusion matrix of true condition versus estimated state, the mean detection delay and the false-alarm rate. Samples and metrics export to CSV.

**Blocked by:** 05, 06, 08.

**Status:** ready-for-agent

- [ ] MAE, RMSE and MAPE match values computed independently on the same samples, to a stated tolerance.
- [ ] MAPE ignores night-time samples where measured power is near zero, and says so on screen.
- [ ] A batch of labelled fault runs (one per fault, on the bundled profile) is scored automatically.
- [ ] The confusion matrix, detection delay and false-alarm rate are shown and exported.
- [ ] The scoring is available from the headless API, and a test checks a known case: a healthy run has no false alarms at the derived thresholds.
- [ ] Export writes samples and metrics to CSV files the user chooses, and works with Windows, macOS and Linux paths.
