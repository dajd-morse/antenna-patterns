# Software Design Document
## ITU-R Antenna Pattern Tool

**Version:** 1.0  
**Date:** 2026-04-25  
**Author:** Dave Morse / Avaliant  

---

## 1. Purpose

This tool generates reference antenna gain patterns per ITU-R Recommendations S.1528, S.672, S.580, and S.465. Given a set of antenna parameters, it plots the gain pattern (dBi vs. angle from boresight), reports the off-boresight angles at standard dB-below-peak contours, and converts those contour angles to scan angles from satellite nadir for a user-specified orbit altitude and ground elevation angle.

The tool is intended for satellite link budget analysis, interference assessment, and frequency coordination under ITU Radio Regulations procedures.

---

## 2. Architecture Overview

```
antenna-patterns/
├── main.py                  Entry point (QApplication + MainWindow)
├── patterns/
│   ├── base.py              AntennaPattern ABC + ParamSpec dataclass
│   ├── s1528.py             ITU-R S.1528 implementation
│   ├── s672.py              ITU-R S.672 implementation
│   ├── s580.py              ITU-R S.580 implementation
│   ├── s465.py              ITU-R S.465 implementation
│   └── __init__.py          PATTERN_REGISTRY list
├── utils/
│   └── geometry.py          Spherical-Earth geometry
└── gui/
    ├── main_window.py       Top-level QMainWindow + QSplitter layout
    ├── input_panel.py       Dynamic parameter input panel (left pane)
    └── plot_widget.py       Matplotlib canvas + results table (right pane)
```

### 2.1 Extension Pattern

To add a new ITU-R recommendation:
1. Create `patterns/sNNNN.py` subclassing `AntennaPattern`.
2. Implement `get_params_spec()` → list of `ParamSpec` and `gain(phi, params)`.
3. Append an instance to `PATTERN_REGISTRY` in `patterns/__init__.py`.

The GUI builds the input panel entirely from `ParamSpec` metadata — no GUI changes required.

---

## 3. Component Design

### 3.1 `patterns/base.py`

#### `ParamSpec` (dataclass)

| Field | Type | Purpose |
|-------|------|---------|
| `name` | str | Key used in the `params` dict |
| `label` | str | Display label in the GUI |
| `type` | `'float'` \| `'choice'` | Widget type to render |
| `default` | Any | Initial value |
| `min` / `max` / `step` | float | Spinner bounds and step |
| `choices` | list[str] | Items for a QComboBox |
| `units` | str | Appended to spinner suffix |
| `tooltip` | str | Widget tooltip |
| `computed` | bool | If True, adds an auto-compute "Calc" button |

#### `AntennaPattern` (ABC)

| Method | Signature | Notes |
|--------|-----------|-------|
| `gain` | `(phi: ndarray, params: dict) → ndarray` | Core computation; phi in degrees from boresight |
| `get_params_spec` | `() → list[ParamSpec]` | Drives GUI generation |
| `suggest_derived` | `(name, params) → float \| None` | Powers the "Calc" button |
| `get_default_params` | `() → dict` | Convenience helper |

### 3.2 Pattern Implementations

#### 3.2.1 ITU-R S.1528

**Applicable to:** Non-geostationary FSS space station transmit/receive antennas.

**Parameters:**

| Symbol | Name | Default | Notes |
|--------|------|---------|-------|
| Gm | Peak gain | 32.3 dBi | Maximum gain at boresight |
| ψb | 3 dB half-beamwidth | 1.0° | User input; Calc button suggests ≈ 32.5/(D/λ) |
| Ls | Sidelobe level | −15 dB | **Relative to peak** (negative value) |
| LF | Far-field floor | 0 dBi | Absolute level |

**Piecewise formula:**

| Region | Condition | Formula |
|--------|-----------|---------|
| Gaussian main lobe | 0 ≤ \|ψ\| ≤ Y | Gm − 3·(ψ/ψb)² |
| Log-taper sidelobe | Y < \|ψ\| ≤ Z | (Gm + Ls) − 25·log₁₀(\|ψ\|/Y) |
| Far-field floor | \|ψ\| > Z | LF |

Transition angles:
- `Y = ψb × sqrt(−Ls / 3)` — angle at which Gaussian drops to Ls below peak; sidelobe formula begins here with gain = Gm + Ls (continuous)
- `Z = Y × 10^(0.04 × (Gm + Ls − LF))` — angle at which log-taper rolloff reaches the floor LF (continuous)

**Example (Gm = 32.3 dBi, ψb = 1.0°, Ls = −15 dB, LF = 0 dBi):**  
Y = 2.236°, Z = 11.00°, gain at Y = 17.3 dBi, gain at Z = 0 dBi.

#### 3.2.2 ITU-R S.672

**Applicable to:** Space station antennas (in-orbit, evaluated in any plane).

**Formula:**

| Region | Condition | Formula |
|--------|-----------|---------|
| Gaussian main lobe | 0 ≤ \|φ\| ≤ φs | Gmax − 12·(φ/φ₀)² |
| Near sidelobe plateau | φs < \|φ\| ≤ φe | Ls |
| Far sidelobe | φe < \|φ\| ≤ 48° | 32 − 25·log₁₀(\|φ\|) |
| Floor | \|φ\| > 48° | −10 dBi |

Where:
- `φ₀` = 3 dB half-beamwidth (user input; "Calc" button fills ≈ 70/(D/λ))
- `φs = φ₀ × sqrt((Gmax − Ls) / 12)` (main lobe → plateau)
- `φe = 10^((32 − Ls) / 25)` (plateau → far sidelobe)

**Ls options:**
- **10 dB below peak** → Ls = Gmax − 10 dBi
- **20 dB below peak** → Ls = Gmax − 20 dBi
- **Custom** → user-specified absolute value (dBi)

#### 3.2.3 ITU-R S.580

**Applicable to:** Earth station antennas in FSS (uplink/downlink to GSO).

Adds an intermediate G₁ plateau between the main lobe and the 32−25log rolloff.

**D/λ ≥ 100:**

| Region | Formula |
|--------|---------|
| Main lobe (0 → φm) | Gmax − 2.5×10⁻³·(D/λ·φ)² |
| G₁ plateau (φm → φ₁) | G₁ = −1 + 15·log₁₀(D/λ) |
| Far sidelobe (φ₁ → 48°) | 32 − 25·log₁₀(φ) |
| Floor (> 48°) | −10 dBi |

φ₁ = max(100/Dλ, 10^((32 − G₁) / 25))

#### 3.2.4 ITU-R S.465

**Applicable to:** Earth station reference pattern for interference assessment (FSS).  
Simpler than S.580 — no intermediate plateau.

| Region | Formula |
|--------|---------|
| Main lobe (0 → φ₁) | Gmax − 2.5×10⁻³·(D/λ·φ)² |
| Far sidelobe (φ₁ → 48°) | 32 − 25·log₁₀(φ) |
| Floor (> 48°) | −10 dBi |

φ₁ is found numerically as the last angle at which the Gaussian main lobe descends through the 32−25log curve.

### 3.3 `utils/geometry.py`

#### Nadir Angle from Elevation Angle

Given a satellite at altitude h above a spherical Earth of radius R = 6371 km, and a ground point seen at elevation angle ε (measured at the ground), the angle from satellite nadir to that ground point is:

```
sin(θ_nadir) = R · cos(ε) / (R + h)
θ_nadir = arcsin(R · cos(ε) / (R + h))
```

This is derived from the law of sines applied to the Earth-centre / satellite / ground-point triangle.

#### Contour Scan Angles from Nadir

The boresight is pointed at the ground point corresponding to the entered elevation angle, so the boresight itself is at angle θ_nadir from nadir. For a dB-below-peak contour at ±φ_dB from boresight, the corresponding nadir scan angles are:

```
θ_contour = θ_nadir + φ_dB    (away from sub-satellite point)
```

The tool reports only the outward direction (increasing nadir angle).

### 3.4 GUI Components

#### `InputPanel` (left pane)

Rebuilds the pattern-parameter form from `get_params_spec()` whenever the pattern dropdown changes. Each `ParamSpec` generates:
- `'float'` → `QDoubleSpinBox` (optionally with a "Calc" auto-compute button)
- `'choice'` → `QComboBox`

Emits `calculate_requested(pattern, pattern_params, common_params)` signal.

Common parameters (always visible):

| Control | Default | Range |
|---------|---------|-------|
| Scan Min | −180° | −180° to 0° |
| Scan Max | +180° | 0° to +180° |
| Orbit Altitude | 500 km | 100–100,000 km |
| Elevation Angle | 90° | 0°–90° |

#### `PlotWidget` (right pane)

- Embeds a `matplotlib` figure with the standard Navigation Toolbar (zoom, pan, etc.)
- Post-plot axis range spinners (X min/max in °, Y min/max in dBi) with "Apply Axes" button
- "Save PNG" triggers `QFileDialog` → `figure.savefig(..., dpi=150)`
- Dotted vertical lines mark each dB contour on the plot
- Results table (read-only, monospace): dB level / angle off boresight / scan angle from nadir

---

## 4. Data Flow

```
User clicks "Calculate & Plot"
        │
        ▼
InputPanel._on_calculate()
  ├── collects pattern_params (from dynamic widgets)
  └── collects common_params (scan range, orbit alt, elev angle)
        │
        ▼  pyqtSignal
PlotWidget.update_plot(pattern, pattern_params, common_params)
  ├── phi = linspace(scan_min, scan_max, 20,000)
  ├── G   = pattern.gain(phi, pattern_params)          ← core math
  ├── Renders plot (matplotlib)
  ├── nadir_angle_from_elevation(elev, orbit_alt)       ← geometry
  └── For each dB level:
        ├── _first_descent(phi≥0, G≥0, gmax − db)      ← contour finder
        └── nadir_scan = θ_nadir + φ_contour            ← results table
```

---

## 5. Verification Checks and Known Limitations

> **These items should be verified against the current published ITU-R Recommendations before using results in coordination filings or interference studies.**

### 5.1 S.1528 Beamwidth Estimate (ψb)

The "Calc" button for ψb uses `32.5 / (D/λ)` where D/λ is derived from peak gain assuming η = 0.6 efficiency. This gives a rough half-power beamwidth estimate. The **actual** 3 dB half-beamwidth of your antenna may differ significantly — it should come from the antenna specification or measured pattern, not from this formula.

*ψb is the most critical input for S.1528: it sets the scale of the entire pattern. Always verify against the real antenna datasheet.*

### 5.2 S.1528 TX vs. RX Distinction

The TX/RX selector is a label only — both modes use the same piecewise formula. The published S.1528 may specify different default Ls values for transmit vs. receive cases.

**Check:** Confirm with the current revision of ITU-R S.1528 whether TX and RX patterns differ, and update `s1528.py` accordingly if so.

### 5.3 S.672 Sidelobe Floor Beyond φe

The implementation floors gain at `Ls − 10 dBi` beyond the plateau (before the 32−25log region is reached). The published S.672-4 pattern may specify a different expression for the far-sidelobe region. Review the recommendation's Table 1 and Fig. 1 to confirm the rolloff beyond φe matches your use case.

### 5.4 S.580 G₁ Plateau Boundary

For D/λ ≥ 100, G₁ = −1 + 15·log₁₀(D/λ). This can exceed Gmax for very small antennas at the boundary. The code guards against this with `g1 = min(g1, gmax − 1)`, but the proper treatment per the recommendation should be confirmed when Gmax is close to the sidelobe floor.

### 5.5 S.465 Transition Angle φ₁

The transition angle φ₁ is found numerically (200,000-point search over 0.05°–90°). There is a spurious crossing at very small angles (< 0.1°) where the 32−25·log(φ) function blows up; the code takes the **last** falling crossing to avoid this artifact. Visual inspection of the plot is recommended to confirm the main lobe / sidelobe transition looks correct for your Gmax.

### 5.6 Validity Range of 32 − 25·log(φ)

The 32−25·log(φ) far-sidelobe formula is defined in the ITU-R recommendations only for φ ≥ 1° (sometimes φ ≥ φ₁ or φ ≥ 100λ/D). The tool evaluates it down to the numerically computed transition angle, which may be less than 1° for large Gmax values. Results below 1° off boresight in the sidelobe region should be treated with caution.

### 5.7 Spherical Earth Model

The geometry uses a mean Earth radius of 6371 km. For precise coordination work, the ITU uses a slightly different value (6378.137 km equatorial / 6356.752 km polar). The difference in nadir angle is < 0.1° for most LEO/MEO altitudes.

### 5.8 Nadir Angle at Low Elevation Angles

As elevation angle ε → 0°, the nadir angle approaches its maximum:

```
θ_nadir_max = arcsin(R / (R + h))
```

At 500 km altitude this is ≈ 68°. The tool allows ε = 0° as input; ensure the satellite can actually see that elevation angle from the specified orbit altitude (a 500 km orbit cannot serve elevation angles below ≈ 0° at great-circle distances beyond ~2600 km from the sub-satellite point).

### 5.9 One-Sided Contour Reporting

The results table reports the **first** (smallest) off-boresight angle at which gain drops through each dB threshold. For patterns with a plateau (Ls region), the gain may be flat across several degrees — the reported angle is the transition from the main lobe into the plateau, not the far edge. This is the physically meaningful "beamwidth at X dB" definition.

### 5.10 Recommendation Revision Status

The formulae are implemented from the versions current as of 2024:
- ITU-R S.1528 (2001, with amendments)
- ITU-R S.672-4 (1997)
- ITU-R S.580-6 (2004)
- ITU-R S.465-6 (2010)

**Check:** Confirm no superseding revisions have been issued by ITU-R Study Group 4 before use in formal coordination.

---

## 6. Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| PyQt6 | ≥ 6.4 | GUI framework |
| matplotlib | ≥ 3.7 | Plot rendering |
| numpy | ≥ 1.24 | Array mathematics |

---

## 7. Future Enhancements

- Direct D/λ input as an alternative to deriving it from Gmax
- Additional patterns: ITU-R S.1855, S.580 variations for VSAT, BO pattern asymmetry
- Overlay mode — plot multiple patterns on the same axes for comparison
- CSV/Excel export of the contour summary table
- Negative elevation angles (satellite elevation below local horizon, for interference geometry)
- 3D radiation pattern cut selection (not just the principal plane)
