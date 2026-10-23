# 09: Validation metrics, fault-detection scoring and export

**What to build:** the Dashboard's Validation tab. For a healthy run it shows MAE, RMSE and MAPE between P measured and P predicted. For a set of labelled fault runs it shows a confusion matrix of true condition versus estimated state, the mean detection delay and the false-alarm rate. Samples and metrics export to CSV.

**Blocked by:** 05, 06, 08.

**Status:** ready-for-agent

- [ ] MAE, RMSE and MAPE match values computed independently on the same samples, to a stated tolerance.
- [ ] MAPE ignores night-time samples where measured power is near zero, and says so on screen.
- [ ] A batch of labelled fault runs (one per fault, on the bundled profile) is scored automatically.
- [ ] The confusion matrix, detection delay and false-alarm rate are shown and exported.
- [ ] The scoring is available from the headless API. A test checks a known case: a healthy run has zero false alarms at the default thresholds (5 and 10 percent).
- [ ] The false-alarm rate at thresholds derived as mean plus 2 and 3 sigma is also computed and shown. It is expected to be non-zero because the healthy deviation distribution is not Gaussian (about 30 Warning and 6 Abnormal of 702 daytime samples on the bundled day). This is a finding to surface, not a failure.
- [ ] Export writes samples and metrics to CSV files the user chooses, and works with Windows, macOS and Linux paths.
