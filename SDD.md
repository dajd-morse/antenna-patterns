# Software Design Document
## ITU-R Antenna Pattern Tool

Version: 1.1  
Date: 2026-04-25

## Purpose

This tool plots antenna gain envelopes from the current in-force ITU-R
recommendations implemented in `patterns/`:

- ITU-R S.1528-0: non-GSO FSS space-station reference patterns
- ITU-R S.672-4: GSO FSS space-station single-feed design-objective pattern
- ITU-R S.580-6: earth-station design objective near the GSO
- ITU-R S.465-6: earth-station reference pattern for coordination and
  interference assessment

Historical superseded pattern variants are intentionally not exposed.

## Architecture

```text
main.py                  QApplication entry point
patterns/base.py         AntennaPattern ABC and ParamSpec metadata
patterns/s1528.py        ITU-R S.1528-0 current reference variants
patterns/s672.py         ITU-R S.672-4 single-feed envelope
patterns/s580.py         ITU-R S.580-6 current design objective
patterns/s465.py         ITU-R S.465-6 current reference pattern
gui/input_panel.py       Dynamic parameter form and comparison controls
gui/plot_widget.py       Matplotlib plotting and contour table
utils/geometry.py        Spherical-Earth nadir-angle helper
utils/aperture.py        Shared D/lambda and psi_b estimators
utils/contours.py        First-descent contour angle finder
```

The "dB below peak" contour table measures from `AntennaPattern.reference_peak`.
Space-station patterns (S.1528, S.672) return their `Gmax`; earth-station
envelopes (S.465, S.580) return `None`, so the plot widget falls back to the
maximum finite gain of the actual curve rather than an estimate-only field.

Each pattern subclass returns a gain array in dBi for off-boresight angles in
degrees. The GUI is generated from `ParamSpec`, so new parameters should be
added in the relevant pattern class first.

The input panel also asks each pattern whether a parameter is applicable via
`is_param_applicable(name, params)`. Inapplicable parameters remain visible but
are disabled/greyed out so the user can see why the form changed without losing
context. This is currently used for S.1528 section-specific `LN`/`Ls` controls
and for S.465 Note 5.

Parameters marked `computed=True` receive a Calc button. Current calculators:

- `D/lambda` from peak gain and aperture efficiency:
  `D/lambda = sqrt(10^(Gmax/10) / eta) / pi`
- S.1528/S.672 beamwidth estimate from `D/lambda`:
  `psi_b = sqrt(1200) / (D/lambda)`, with S.1528 applying `z` for the
  major-axis plane

## Result Geometry

The contour table reports both the angle off antenna boresight and the scan
angle from satellite nadir. The scan angle from nadir is:

```text
scan_from_nadir = theta_min_elevation + angle_off_boresight
```

where `theta_min_elevation` is computed from the orbit altitude and minimum
ground elevation angle:

```text
theta_min_elevation = asin(R * cos(min_elevation) / (R + orbit_altitude))
```

The Notes column displays the base scan term so identical-looking values are
easy to diagnose when the minimum elevation angle is 90 degrees.

## Implemented Formula Scope

### S.1528-0

The tool exposes:

- Section 1.2 multiple-beam envelope:
  - main lobe: `Gm - 3 * (psi / psi_b)^alpha`
  - near sidelobe shelves using `LN`, `z`, `a`, and `b`
  - far sidelobe: `X - 25 log10(psi)`
  - far-out level `LF` and back-lobe level `LB`
- Section 1.3 simplified masks:
  - `D/lambda < 35`
  - LEO, with `Ls = -6.75` and `Y = 1.5 psi_b`
  - MEO, with `Ls = -12` and `Y = 2 psi_b`

The `psi_b` Calc button uses the S.1528 expression
`sqrt(1200) / (D/lambda)`, multiplied by `z` for the major-axis plane.
Measured or manufacturer beamwidth values should be used when available.

The section 1.2 `LN` control is greyed out for section 1.3 variants. The
section 1.3 `Ls` control is active only for the `D/lambda < 35` variant,
because the LEO and MEO variants define fixed `Ls` values.

The section 1.4 Taylor fitting model is not implemented in this GUI because it
requires additional fitting inputs rather than a simple reference envelope.

### S.672-4

The tool implements the current single-feed circular/elliptical design
objective from recommends 1:

- `Gm - 3 * (psi / psi_b)^alpha`
- `Gm + LN + 20 log10(z)`
- `Gm + LN`
- `X - 25 log10(psi)`
- `LF = 0 dBi`
- `LB = max(15 + LN + 0.25 Gm + 5 log10(z), 0)`

S.672-4 defines numeric single-feed coefficients for `LN = -20 dB` and
`LN = -25 dB`. The tool does not expose `LN = -30 dB` because the
recommendation states that its `a` and `alpha` values require further study.

### S.580-6

For `D/lambda >= 50`, the current design objective is:

- `29 - 25 log10(phi)` for `phi_min <= phi <= 20 deg`
- `-3.5 dBi` for `20 deg < phi <= 26.3 deg`
- S.465 reference segment `32 - 25 log10(phi)` for `26.3 deg < phi < 48 deg`
- `-10 dBi` for `48 deg <= phi <= 180 deg`

where `phi_min = max(1 deg, 100 / (D/lambda))`.

### S.465-6

The current reference pattern is:

- `32 - 25 log10(phi)` for `phi_min <= phi < 48 deg`
- `-10 dBi` for `48 deg <= phi <= 180 deg`

The default `phi_min` is:

- `max(1 deg, 100 / (D/lambda))` for `D/lambda >= 50`
- `max(2 deg, 114 * (D/lambda)^-1.09)` for `D/lambda < 50`

The optional current Note 5 mode uses `phi_min = 2.5 deg` for receiving
earth-station coordination with `D/lambda < 33.3`.

The Note 5 selector is greyed out when `D/lambda >= 33.3`, where the note is
not applicable.

## Verification

`tests/test_patterns.py` contains numeric checks at selected transition points
and policy checks that superseded S.465/S.580 modes are not exposed.

Run:

```powershell
python -m unittest discover -s tests
```

## Useful Future Improvements

- Import measured antenna patterns and overlay them against the ITU masks.
- Export plotted data and contour summaries to CSV.
- Add separate minor-axis and major-axis overlay plots for elliptical beams.
