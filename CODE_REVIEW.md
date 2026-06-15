# Adversarial Code Review — ITU-R Antenna Pattern Tool

**Date:** 2026-06-15
**Reviewer:** Claude (adversarial review)
**Scope:** `patterns/`, `gui/`, `utils/`, `tests/`, `main.py`, repo hygiene

This review is deliberately critical. It assumes the code is wrong until proven
otherwise and focuses on correctness traps, hidden coupling, and maintainability
risks rather than restating what already works. Items are grouped by severity.
Each item gives a concrete location and a suggested fix.

All 9 unit tests currently pass (`python -m unittest discover -s tests` → OK).
The issues below are mostly things the existing tests do **not** exercise.

---

## Severity legend

| Tag | Meaning |
|-----|---------|
| 🔴 High | Wrong results, silent data corruption, or crash-prone in normal use |
| 🟠 Medium | Misleading output, hidden coupling, or maintenance landmine |
| 🟡 Low | Cleanup, hygiene, polish |
| 🔬 Verify | Possible formula/standard deviation — confirm against the ITU-R text |

---

## 🔴 High severity

### H1. `gmax` parameter is silently used as the contour "peak" even where it is documented as estimate-only
`gui/plot_widget.py:159-168` and `:184`

```python
if 'gmax' in pattern_params:
    gmax = float(pattern_params['gmax'])
else:
    gmax = float(np.nanmax(G)) ...
...
angle = first_descent(phi_pos, G_pos, gmax - db)
```

For **S.465** and **S.580**, `gmax` is described in the `ParamSpec` tooltip as
*"Used only for estimating D/lambda from peak gain"* (`patterns/s465.py:24`,
`patterns/s580.py:27`). But because the param is literally named `gmax`, the plot
widget adopts it as the reference peak for the entire "dB Below Peak" contour
table. Those patterns' curves do **not** peak at `gmax` — S.465 peaks at the
constant `32 - 25·log10(phi_min)` (≈32 dBi), independent of the user's `gmax`
estimate (default 32.3). The contour rows ("−2 dB", "−4 dB", …) are therefore
measured below a number that is not the curve's actual peak, so every reported
angle is subtly wrong and changes if the user edits an "estimate-only" field.

**Fix:** Decide on one definition of "peak." Either (a) always derive the peak
from the plotted curve (`np.nanmax(G)`), or (b) only treat `gmax` as the peak for
patterns where it genuinely is the main-lobe gain (S.1528, S.672). A clean
approach: add a `peak_gain(params)` method on `AntennaPattern` so each pattern
declares its own reference, instead of the plot widget guessing from a dict key.

### H2. No validation produces non-physical (rising) envelopes for valid-looking inputs
`patterns/s1528.py:126-168`, `patterns/s672.py:80-121`

`LF` (far-out sidelobe, default **0 dBi**) is independent of `Gmax` and `LN`.
When `Gmax` is small, the near-in sidelobe shelf `Gm + LN` falls **below** `LF`,
and the intermediate `X − 25·log10(phi)` region collapses entirely. Verified:

```
gmax=20, ln=-25, psi_b=1, lf=0  ->  y = 3.99 < b·psi_b = 6.32
near-sidelobe shelf = Gm+LN = -5 dBi, but far-out LF = 0 dBi
g(phi≈10°) = 0.0 dBi   # envelope RISES with angle — non-physical
```

The tool will happily plot an antenna whose gain *increases* off-axis. There is
no warning and no clamp. `param_warning()` only checks the `z`/`LN` `a`-coefficient
case, not this one.

**Fix:** Add a `param_warning` (or a hard clamp) when `LF > Gm + LN`, and/or when
`y < b·psi_b` (the X-region collapses). At minimum surface it to the user.

### H3. `tests/` and `utils/contours.py` are untracked — core logic is uncommitted
`git status` shows `tests/` and `utils/contours.py` as `??` (untracked).

The contour-finding function (`first_descent`) that drives the entire results
table, and the *only* test file in the project, are not under version control.
A `git clean` or a fresh clone loses them. The repo's last commit message
("Fix layout overlap and contour-line checkbox") implies recent work, so this is
likely an oversight rather than intent.

**Fix:** `git add tests/ utils/contours.py` and commit, or `.gitignore` them
deliberately if they are truly scratch (they are not — they are imported by
shipping code).

---

## 🟠 Medium severity

### M1. Dead, divergent duplicate of the contour finder
`gui/plot_widget.py:321-335`

`_first_descent` is defined but never called — the live code path uses
`first_descent` imported from `utils/contours.py` (confirmed by grep: the only
references to `_first_descent` are its own definition). Worse, the two
implementations differ:

- `utils/contours.first_descent`: `if g0 > target and g1 <= target` + a trailing
  end-of-array equality check.
- `plot_widget._first_descent`: `if g0 > target >= g1`, no trailing check.

A future reader cannot tell which is authoritative. Delete the dead copy.

### M2. Helper functions copy-pasted across four pattern modules (+ inline in GUI)
`patterns/s1528.py:35`, `patterns/s672.py:20`, `patterns/s580.py:16`,
`patterns/s465.py:13`, and again inline at `gui/input_panel.py:301-308`

`_d_lambda_from_gmax()` is duplicated verbatim in all four pattern files.
`_psi_b_from_d_lambda()` is duplicated in two. The compare-panel re-implements
both formulas inline (`_calc_compare_d_lambda`, `_calc_compare_psi_b`). Five
copies of `sqrt(10^(G/10)/eta)/pi` means five places to fix if the aperture
formula ever changes — exactly the kind of drift that produces inconsistent
results between the per-pattern Calc buttons and the compare panel.

**Fix:** Move both helpers to `utils/` (e.g. `utils/aperture.py`) and import them
everywhere, including the GUI compare path.

### M3. Compare mode silently disagrees with single-pattern mode
`gui/plot_widget.py:214-260`, `gui/input_panel.py:310-319`

- It hardcodes `'axis': 'Minor axis'` for S.1528, so the major-axis `psi_b`
  scaling (`× z`) that the single-pattern Calc button applies is never used —
  yet it *does* pass `z` into the gain function. The two modes give different
  curves for the same physical antenna when `z > 1`.
- The compare `D/lambda` spin floor is **50** (`input_panel.py:95`), but the
  per-pattern S.465 form allows `D/lambda` down to 1 (`s465.py:29`). Small
  dishes can be plotted individually but not compared.
- `gmax` is passed to S.465/S.580's labels but those curves ignore it (see H1),
  so the legend implies a dependency that does not exist.

**Fix:** Drive compare mode through the same parameter-collection and
`suggest_derived` path the single-pattern form uses, rather than a parallel
hand-rolled dict, so the two can never diverge.

### M4. No error handling around plotting or file save
`gui/plot_widget.py:149-210`, `:310-316`

`update_plot` calls `pattern.gain(...)` directly with no try/except. A
`KeyError`/`ValueError` from a malformed param dict propagates to the Qt event
loop (ugly traceback, no user feedback). `_save_png` calls `self._figure.savefig`
with no guard — an unwritable path or locked file throws and is swallowed by Qt.

**Fix:** Wrap both in try/except and show a `QMessageBox` with the error.

### M5. Y-axis floor is hardcoded to −20 dBi and can clip the curve
`gui/plot_widget.py:167`, `:207`

```python
self._ymin_spin.setValue(-20.0)
self._ax.set_ylim(-20.0, gmax + 5.0)
```

S.465/S.580 have a −10 dBi floor (fine), but S.1528/S.672 back-lobe `LB` is
clamped to ≥0 while far-out shelves and the −25·log10 tail can run well below
−20 dBi for small `psi_b`. The curve is then drawn clipped at the bottom with no
indication. Compare mode computes a data-driven `ymin` (`:271`) — the
single-pattern path should do the same instead of a magic constant.

### M6. Tests don't cover the risk-prone paths
`tests/test_patterns.py`

Good coverage of S.672/S.1528 §1.2 boundaries and policy (no `-30 dB`, no `era`).
But nothing exercises:
- **S.1528 §1.3** LEO/MEO/`D/lambda<35` masks (`_gain_section_13`) — entirely
  untested, including the `ls >= 0 → -0.01` guard and the `z` shadow variable.
- The `first_descent` **floor/end-of-array equality** branch (`contours.py:22`)
  and the NaN-skip behavior.
- `nadir_angle_from_elevation` only at two points; the `np.clip` saturation
  branch and `max_elevation_angle` are untested.
- Any GUI logic (`is_param_applicable` wiring, compare-mode dict construction).

**Fix:** Add §1.3 numeric checks (continuity at `Y = 1.5·psi_b`/`2·psi_b`), a
floor-equality contour test, and the malformed-envelope cases from H2.

---

## 🟡 Low severity

### L1. Scratch/duplicate source committed to the repo
`inputs/script.py`, `inputs2/itu_antenna_patterns.py`, `inputs2/script.py`,
`inputs2/compare/`, `inputs2/perplexity.txt`

~370 lines of earlier standalone implementations are committed alongside the real
package. They are not referenced by `main.py` or the package, but they shadow the
"current" formulas and will confuse anyone grepping for, say, `s580` logic.

**Fix:** Move to a `scratch/` dir excluded from packaging, or delete.

### L2. `_save_png` has no overwrite/extension safeguards
`gui/plot_widget.py:310-316` — accepts any path, no `.png` enforcement, no
confirmation. Minor, but combine with M4's missing error handling.

### L3. `requirements.txt` has only lower bounds
`requirements.txt:1-3` — `PyQt6>=6.4.0` etc. with no upper pin. A future PyQt6
major could break the `Qt.AlignmentFlag`/`QtAgg` imports without notice. Consider
`>=,<` ranges or a lockfile for reproducibility.

### L4. Reused/shadowed variable name `z`
`patterns/s1528.py:194` — `z = y * 10.0 ** (...)` reuses `z`, which elsewhere in
the same class means the beam axis ratio. In §1.3 the axis ratio is unused so
there is no bug, but it is a readability trap. Rename to `phi_far` or similar.

### L5. Legacy `elev_angle` fallback key is dead weight
`gui/plot_widget.py:153` — `common_params.get('min_elev_angle',
common_params.get('elev_angle', 90.0))`. `_common_params()` only ever emits
`min_elev_angle`, so the `elev_angle` fallback is unreachable. Remove it or
document why it's kept.

---

## 🔬 Verify against ITU-R text (not necessarily bugs)

These match a plausible reading of the standards but I could not confirm the
exact coefficients/boundaries from the source documents. Worth a second pass with
the recommendation PDFs open.

### V1. S.1528 §1.2 inner shelf is *higher* than the outer shelf for `z > 1`
`patterns/s1528.py:161-162` — region `(a·psi_b, 0.5·b·psi_b]` is
`Gm + LN + 20·log10(z)` while `(0.5·b·psi_b, b·psi_b]` is `Gm + LN`. For `z > 1`
the inner sidelobe sits *above* the near shelf. Confirm the `+20·log10(z)` sign
and that it applies to the inner segment.

### V2. Major-axis `psi_b` multiplies by `z`
`patterns/s1528.py:30-32` — `_psi_b_from_d_lambda` does `psi_b *= max(z,1.0)` for
the major axis. Confirm whether the elliptical relationship multiplies or divides
by the axis ratio for the plane in question.

### V3. S.1528 §1.3 mixes `Gm` (main lobe) with `D/lambda`-absolute sidelobe levels
`patterns/s1528.py:177-203` — the main lobe uses `Gm`, but the LEO/MEO sidelobe
region uses `20·log10(D/lambda) + 5.65/3.5`. If the user's `Gmax` and `D/lambda`
are inconsistent, there is a discontinuity at `Y`. This is inherent to the
standard's formulation, but the UI should probably warn when `Gmax` and the
`D/lambda`-implied gain disagree by more than a few dB.

### V4. S.580-6 segment boundaries (`20°`, `26.3°`, `48°`) and the `-3.5 dBi` plateau
`patterns/s580.py:60-69` — the segmentation looks self-consistent (the pieces are
roughly continuous), but confirm the `26.3°` switch point and that the
`32 − 25·log10(phi)` (S.465) borrow over `26.3–48°` is the intended current
S.580-6 envelope rather than a flat floor.

---

## Summary of recommended actions (priority order)

1. **Commit `tests/` and `utils/contours.py`** (H3) — prevent data loss.
2. **Fix the contour "peak" definition** (H1) — wrong numbers in the results table.
3. **Validate / warn on non-physical envelopes** (H2).
4. **Delete dead `_first_descent`** (M1) and **de-duplicate the aperture helpers** (M2).
5. **Unify compare mode with the single-pattern path** (M3) and **add error handling** (M4).
6. **Expand tests** to §1.3, contour edge cases, and the malformed-envelope inputs (M6).
7. Clean up scratch dirs (L1) and verify the ITU coefficient items (V1–V4) against source.
