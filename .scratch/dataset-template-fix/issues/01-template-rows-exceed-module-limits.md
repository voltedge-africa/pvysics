# Dataset template example rows are physically impossible for the generic module

Status: resolved
Found: 2026-10-30, while checking a dashboard screenshot against a ChatGPT review

## Symptom

Importing `docs/templates/pvysics-dataset-template.csv` (or the Template… button's file) and pressing
Analyse or Replay on Dashboard gives `SYSTEM STATE: ABNORMAL`, deviation about +17.7 %, on a file
that is supposed to be a clean example.

## Cause

The five rows in `TEMPLATE_ROWS` (`src/pvysics/dataset.py`) were written by hand, never run through the
twin. For the generic 60-cell 250 W module every row has

- current above Isc (e.g. 6.02 A at 612 W/m2, where Isc is 5.47 A), and
- measured power above the module's maximum power (e.g. 175.2 W against an MPP of 148.0 W).

Last row: 638 W/m2, 32.3 C, 29.0 V, 6.25 A = 181.2 W; twin MPP there is 154.0 W (Isc 5.70 A).
The twin is right; the example data is impossible. The same numbers appear in the 0.3.0 Windows and
Debian builds and in the manual's Dataset chapter.

## Not the cause (checked)

- Predicting at the measured voltage instead of the MPP (ChatGPT's suggestion) would change this row
  from 154.025 W to 154.022 W. It does not explain the symptom.
- Ambient versus module temperature would lower the prediction (140.5 W if 32.3 C were ambient and
  NOCT 45), making the deviation larger.

## Fix

1. Derive the example rows from `solve_curve` for the generic module, so they are consistent by construction.
2. Regenerate `docs/templates/pvysics-dataset-template.{csv,xlsx}`.
3. Test: the template scores Normal on every row with the default limits, and no row exceeds Isc or MPP.
4. Check the manual and screenshots that quote template numbers.
5. Rebuild 0.3.0 (unpublished) so the shipped template is correct.

## Separate, not in this ticket

- Predict at the measured voltage for imported data (design choice; it would hide a stuck MPP tracker).
- Module versus ambient temperature for imported data.
- Realistic synthetic test datasets (clear sky, changing clouds, hot day, partial shading).

## Comments

- Independent check by an OpenCode agent (DeepSeek V4.1 Flash Free) confirmed the arithmetic above.
- Resolved in 4465e47 (template rows and tests). The follow-ups below were done in the next commits.
