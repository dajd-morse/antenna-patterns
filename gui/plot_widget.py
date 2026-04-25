import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QGroupBox,
    QLabel, QDoubleSpinBox, QPushButton, QCheckBox,
    QFileDialog, QHeaderView, QAbstractItemView,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from patterns.s1528 import S1528Pattern
from patterns.s672  import S672Pattern
from patterns.s465  import S465Pattern
from patterns.s580  import S580Pattern
from utils.geometry import nadir_angle_from_elevation

DB_LEVELS = [2, 4, 6, 8, 10, 15, 20]

# Colours for dB contour lines
_CONTOUR_COLORS = [
    '#e06c00', '#c00000', '#800080', '#006600',
    '#0055aa', '#aa0055', '#005555',
]

# Colours for compare-mode pattern curves
_COMPARE_COLORS = {
    'S.1528': '#1f77b4',
    'S.672':  '#d62728',
    'S.465':  '#2ca02c',
    'S.580':  '#ff7f0e',
    'S.465 legacy': '#8c564b',
    'S.580 pre-1995': '#9467bd',
}


class PlotWidget(QWidget):
    """Right-hand pane: matplotlib plot + gain-contour results table."""

    def __init__(self):
        super().__init__()
        self._setup_ui()

    # ------------------------------------------------------------------ layout

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # ── plot area ────────────────────────────────────────────────────────
        plot_container = QWidget()
        plot_layout = QVBoxLayout(plot_container)
        plot_layout.setContentsMargins(0, 0, 0, 0)

        self._figure = Figure(figsize=(10, 5), tight_layout=True)
        self._canvas = FigureCanvas(self._figure)
        self._ax     = self._figure.add_subplot(111)
        self._toolbar = NavigationToolbar(self._canvas, self)

        # axis range controls + options row
        ctrl = QWidget()
        ctrl_layout = QHBoxLayout(ctrl)
        ctrl_layout.setContentsMargins(4, 0, 4, 0)

        self._xmin_spin = self._axis_spin(-180, -180, 180, '°')
        self._xmax_spin = self._axis_spin( 180, -180, 180, '°')
        self._ymin_spin = self._axis_spin( -20, -120, 100, 'dBi')
        self._ymax_spin = self._axis_spin(  40, -120, 100, 'dBi')

        for lbl, w in [
            ("X min:", self._xmin_spin), ("X max:", self._xmax_spin),
            ("Y min:", self._ymin_spin), ("Y max:", self._ymax_spin),
        ]:
            ctrl_layout.addWidget(QLabel(lbl))
            ctrl_layout.addWidget(w)

        apply_btn = QPushButton("Apply Axes")
        apply_btn.clicked.connect(self._apply_axes)
        ctrl_layout.addWidget(apply_btn)

        save_btn = QPushButton("Save PNG…")
        save_btn.clicked.connect(self._save_png)
        ctrl_layout.addWidget(save_btn)

        self._show_contours_cb = QCheckBox("Show contour lines")
        self._show_contours_cb.setChecked(True)
        self._show_contours_cb.setToolTip(
            "Draw dotted vertical lines at each dB-below-peak contour angle"
        )
        ctrl_layout.addWidget(self._show_contours_cb)
        ctrl_layout.addStretch()

        plot_layout.addWidget(self._toolbar)
        plot_layout.addWidget(self._canvas, 1)
        plot_layout.addWidget(ctrl)

        # ── results table ─────────────────────────────────────────────────────
        results_grp = QGroupBox("Gain Contour Summary")
        results_layout = QVBoxLayout(results_grp)
        results_layout.setContentsMargins(4, 4, 4, 4)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels([
            "dB Below Peak",
            "Angle Off Boresight (°)",
            "Scan Angle from Nadir (°)",
            "Notes",
        ])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setRowCount(len(DB_LEVELS))

        mf = QFont("Courier New", 9)
        for row, db in enumerate(DB_LEVELS):
            item = QTableWidgetItem(f"−{db:2d} dB")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setFont(mf)
            self._table.setItem(row, 0, item)

        results_layout.addWidget(self._table)

        splitter.addWidget(plot_container)
        splitter.addWidget(results_grp)
        splitter.setSizes([560, 200])
        layout.addWidget(splitter)

    @staticmethod
    def _axis_spin(value, lo, hi, units) -> QDoubleSpinBox:
        w = QDoubleSpinBox()
        w.setRange(lo, hi)
        w.setValue(value)
        w.setSingleStep(1.0)
        w.setDecimals(1)
        w.setSuffix(f'  {units}')
        w.setMaximumWidth(110)
        return w

    # --------------------------------------------------------- single pattern

    def update_plot(self, pattern, pattern_params: dict, common_params: dict):
        scan_min  = common_params['scan_min']
        scan_max  = common_params['scan_max']
        orbit_alt = common_params['orbit_alt']
        elev_angle = common_params['elev_angle']

        phi = np.linspace(scan_min, scan_max, 20_000)
        G   = pattern.gain(phi, pattern_params)

        # Peak gain: use explicit param if present, else max finite value
        if 'gmax' in pattern_params:
            gmax = float(pattern_params['gmax'])
        else:
            gmax = float(np.nanmax(G)) if np.any(np.isfinite(G)) else 0.0

        # Sync axis range spinners
        self._xmin_spin.setValue(scan_min)
        self._xmax_spin.setValue(scan_max)
        self._ymin_spin.setValue(-20.0)
        self._ymax_spin.setValue(round(gmax + 5.0, 1))

        self._ax.clear()
        self._ax.plot(phi, G, color='steelblue', linewidth=1.5, label=pattern.name)
        self._ax.axhline(y=gmax, color='gray', linewidth=0.6,
                         linestyle='--', alpha=0.5)

        # Contour lines and table
        phi_pos = phi[phi >= 0]
        G_pos   = G[phi >= 0]
        show_contours = self._show_contours_cb.isChecked()
        theta_nadir   = nadir_angle_from_elevation(elev_angle, orbit_alt)
        mf = QFont("Courier New", 9)

        for row, (db, color) in enumerate(zip(DB_LEVELS, _CONTOUR_COLORS)):
            angle = _first_descent(phi_pos, G_pos, gmax - db)
            if angle is not None:
                if show_contours:
                    self._ax.axvline(x= angle, color=color, linewidth=0.8,
                                     linestyle=':', alpha=0.7)
                    self._ax.axvline(x=-angle, color=color, linewidth=0.8,
                                     linestyle=':', alpha=0.7)
                nadir_scan = theta_nadir + angle
                self._table.setItem(row, 1, _cell(f"{angle:.3f}", mf))
                self._table.setItem(row, 2, _cell(f"{nadir_scan:.3f}", mf))
                self._table.setItem(row, 3, _cell("", mf))
            else:
                self._table.setItem(row, 1, _cell("N/A", mf))
                self._table.setItem(row, 2, _cell("N/A", mf))
                self._table.setItem(row, 3, _cell("beyond scan range / floor", mf))

        self._ax.set_xlabel("Angle from Boresight (degrees)")
        self._ax.set_ylabel("Gain (dBi)")
        self._ax.set_title(f"{pattern.name} — Antenna Gain Pattern")
        self._ax.set_xlim(scan_min, scan_max)
        self._ax.set_ylim(-20.0, gmax + 5.0)
        self._ax.grid(True, alpha=0.3)
        self._ax.legend(loc='upper right', fontsize=9)
        self._canvas.draw()

    # --------------------------------------------------------- compare mode

    def compare_plot(self, compare_params: dict, common_params: dict):
        scan_min  = common_params['scan_min']
        scan_max  = common_params['scan_max']
        orbit_alt = common_params['orbit_alt']
        elev_angle = common_params['elev_angle']

        gmax    = compare_params['gmax']
        ls      = compare_params['ls']
        psi_b   = compare_params['psi_b']
        psi0    = compare_params['psi0']
        dλ      = compare_params['d_over_lambda']
        legacy  = compare_params['include_legacy']

        phi = np.linspace(scan_min, scan_max, 20_000)

        curves: list[tuple[str, np.ndarray]] = []

        # S.1528
        p1528 = S1528Pattern()
        G1528 = p1528.gain(phi, {'gmax': gmax, 'psi_b': psi_b, 'ls': ls,
                                  'lf': 0.0, 'mode': 'Transmit'})
        curves.append((f"S.1528  Gm={gmax} dBi, Ls={ls:g} dB", G1528))

        # S.672 — Ls must be -20, -25, or -30
        valid_ls = [-20.0, -25.0, -30.0]
        ls672 = min(valid_ls, key=lambda v: abs(v - ls))
        ls672_str = f"{ls672:g} dB"
        p672 = S672Pattern()
        G672 = p672.gain(phi, {'gmax': gmax, 'psi0': psi0,
                                'ls': f"{ls672:g} dB"})
        label672 = f"S.672   Gm={gmax} dBi, Ls={ls672:g} dB"
        if ls672 != ls:
            label672 += f"  (snapped from {ls:g})"
        curves.append((label672, G672))

        # S.465 modern
        p465 = S465Pattern()
        G465 = p465.gain(phi, {'d_over_lambda': dλ, 'era': 'Post-1993 (modern)'})
        curves.append((f"S.465   D/λ={dλ:g}", G465))

        # S.580 post-1995
        p580 = S580Pattern()
        G580 = p580.gain(phi, {'d_over_lambda': dλ, 'era': 'Post-1995'})
        curves.append((f"S.580   D/λ={dλ:g}", G580))

        if legacy:
            G465_leg = p465.gain(phi, {'d_over_lambda': dλ,
                                       'era': 'Pre-1993 (legacy Note 4)'})
            curves.append((f"S.465 legacy  D/λ={dλ:g}", G465_leg))
            G580_pre = p580.gain(phi, {'d_over_lambda': dλ, 'era': 'Pre-1995'})
            curves.append((f"S.580 pre-1995  D/λ={dλ:g}", G580_pre))

        # Plot
        self._ax.clear()
        default_colors = list(_COMPARE_COLORS.values())
        for i, (label, G) in enumerate(curves):
            color = default_colors[i % len(default_colors)]
            self._ax.plot(phi, G, linewidth=1.5, color=color, label=label)

        # Axis limits: use gmax + 5 top, finite min − 3 bottom
        all_finite = np.concatenate([
            G[np.isfinite(G)] for _, G in curves if np.any(np.isfinite(G))
        ])
        ymin = float(np.nanmin(all_finite)) - 3.0 if all_finite.size else -20.0
        ymax = gmax + 5.0

        self._xmin_spin.setValue(scan_min)
        self._xmax_spin.setValue(scan_max)
        self._ymin_spin.setValue(round(ymin, 1))
        self._ymax_spin.setValue(round(ymax, 1))

        self._ax.set_xlim(scan_min, scan_max)
        self._ax.set_ylim(ymin, ymax)
        self._ax.set_xlabel("Angle from Boresight (degrees)")
        self._ax.set_ylabel("Gain (dBi)")
        self._ax.set_title("ITU-R Antenna Pattern Comparison")
        self._ax.grid(True, alpha=0.3)
        self._ax.legend(loc='upper right', fontsize=8)
        self._canvas.draw()

        # Clear the contour table — not meaningful for multi-pattern view
        mf = QFont("Courier New", 9)
        for row in range(len(DB_LEVELS)):
            self._table.setItem(row, 1, _cell("—", mf))
            self._table.setItem(row, 2, _cell("—", mf))
            self._table.setItem(row, 3, _cell("compare mode", mf))

    # ----------------------------------------------------------------- axes

    def _apply_axes(self):
        self._ax.set_xlim(self._xmin_spin.value(), self._xmax_spin.value())
        self._ax.set_ylim(self._ymin_spin.value(), self._ymax_spin.value())
        self._canvas.draw()

    def _save_png(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Antenna Pattern Plot", "antenna_pattern.png",
            "PNG Images (*.png);;All Files (*)"
        )
        if path:
            self._figure.savefig(path, dpi=150, bbox_inches='tight')


# ------------------------------------------------------------------ utilities

def _first_descent(phi: np.ndarray, G: np.ndarray, target: float) -> float | None:
    """
    Return the first angle where G descends through target (linear interpolation).
    NaN values are skipped — they do not trigger a crossing.
    """
    for i in range(len(G) - 1):
        g0, g1 = G[i], G[i + 1]
        if np.isnan(g0) or np.isnan(g1):
            continue
        if g0 >= target > g1:
            t = (target - g0) / (g1 - g0)
            return float(phi[i] + t * (phi[i + 1] - phi[i]))
    return None


def _cell(text: str, font: QFont) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    item.setFont(font)
    return item
