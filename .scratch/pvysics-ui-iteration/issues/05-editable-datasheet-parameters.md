# 05: Editable datasheet parameters with reset

**What to build:** the Setup tab's module datasheet section gets editable fields for Isc, Voc, Impp, Vmpp, Ki, Kv and Ns, filled from the active datasheet. A "Reset to generic module" button restores the generic 60-cell, 250 W values. Edits take effect on Apply and start, like other setup values, and the Model tab shows the new fitted parameters.

**Blocked by:** None (can start immediately).

**Status:** done

- [x] Fields show the active datasheet whether it came from the generic module or a file.
- [x] Validation rejects non-positive values, Vmpp not below Voc, Impp not below Isc, a non-integer or non-positive Ns, and a datasheet the diode fit cannot fit, each with a specific message; the previous datasheet stays active.
- [x] Reset to generic module restores the defaults and updates the fields.
- [x] Nothing applies until Apply and start; the Run summary shows the edited values.
- [x] A run with an edited module gives different, physically sensible power (a test compares STC power with the edited Pmpp within the existing tolerance).
- [x] Loading a datasheet file still works and fills the fields.
- [x] Invalid values are logged if the log pane exists.
- [x] Offscreen smoke test edits a value, applies, and sees the Model tab parameters change.
