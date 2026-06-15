import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QGroupBox,
    QLabel, QDoubleSpinBox, QPushButton, QCheckBox,
    QFileDialog, QHeaderView, QAbstractItemView, QMessageBox,
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
from utils.contours import first_descent

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
}


class PlotWidget(QWidget):
    """Right-hand pane: matplotlib plot + gain-contour results table."""

    def __init__(self):
        super().__init__()
        self._contour_lines: list = []   # vertical line artists for show/hide
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

        self._figure = Figure(tight_layout=True)   # no fixed figsize — Qt controls sizing
        self._canvas = FigureCanvas(self._figure)
        self._canvas.setMinimumWidth(400)
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
            "Show/hide dotted vertical lines at each dB-below-peak contour angle"
        )
        self._show_contours_cb.stateChanged.connect(self._toggle_contour_lines)
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
        min_elev_angle = common_params['min_elev_angle']

        phi = np.linspace(scan_min, scan_max, 20_000)
        try:
            G = pattern.gain(phi, pattern_params)
        except Exception as exc:  # surface bad params instead of a raw traceback
            QMessageBox.critical(self, "Plot error",
                                 f"Could not evaluate {pattern.name}:\n{exc}")
            return

        # Reference peak for "dB below peak" contours: the pattern decides, else
        # fall back to the maximum finite gain of the actual curve.
        ref_peak = pattern.reference_peak(pattern_params)
        if ref_peak is None:
            ref_peak = float(np.nanmax(G)) if np.any(np.isfinite(G)) else 0.0
        gmax = float(ref_peak)

        # Data-driven y-range so low sidelobes/back-lobes are not silently clipped
        finite = G[np.isfinite(G)]
        ymin = min(-20.0, float(np.nanmin(finite)) - 3.0) if finite.size else -20.0
        ymax = round(gmax + 5.0, 1)

        # Sync axis range spinners
        self._xmin_spin.setValue(scan_min)
        self._xmax_spin.setValue(scan_max)
        self._ymin_spin.setValue(round(ymin, 1))
        self._ymax_spin.setValue(ymax)

        self._ax.clear()
        self._ax.plot(phi, G, color='steelblue', linewidth=1.5, label=pattern.name)
        self._ax.axhline(y=gmax, color='gray', linewidth=0.6,
                         linestyle='--', alpha=0.5)

        # Contour lines and table
        phi_pos = phi[phi >= 0]
        G_pos   = G[phi >= 0]
        show_contours = self._show_contours_cb.isChecked()
        theta_nadir   = nadir_angle_from_elevation(min_elev_angle, orbit_alt)
        mf = QFont("Courier New", 9)

        self._contour_lines.clear()
        for row, (db, color) in enumerate(zip(DB_LEVELS, _CONTOUR_COLORS)):
            angle = first_descent(phi_pos, G_pos, gmax - db)
            if angle is not None:
                # Always draw; visibility controlled by checkbox
                l1 = self._ax.axvline(x= angle, color=color, linewidth=0.8,
                                      linestyle=':', alpha=0.7,
                                      visible=show_contours)
                l2 = self._ax.axvline(x=-angle, color=color, linewidth=0.8,
                                      linestyle=':', alpha=0.7,
                                      visible=show_contours)
                self._contour_lines.extend([l1, l2])
                nadir_scan = theta_nadir + angle
                self._table.setItem(row, 1, _cell(f"{angle:.3f}", mf))
                self._table.setItem(row, 2, _cell(f"{nadir_scan:.3f}", mf))
                self._table.setItem(row, 3, _cell(f"base scan {theta_nadir:.3f}", mf))
            else:
                self._table.setItem(row, 1, _cell("N/A", mf))
                self._table.setItem(row, 2, _cell("N/A", mf))
                self._table.setItem(row, 3, _cell("beyond scan range / floor", mf))

        self._ax.set_xlabel("Angle from Boresight (degrees)")
        self._ax.set_ylabel("Gain (dBi)")
        self._ax.set_title(f"{pattern.name} — Antenna Gain Pattern")
        self._ax.set_xlim(scan_min, scan_max)
        self._ax.set_ylim(ymin, ymax)
        self._ax.grid(True, alpha=0.3)
        self._ax.legend(loc='upper right', fontsize=9)
        self._canvas.draw()

    # --------------------------------------------------------- compare mode

    def compare_plot(self, compare_params: dict, common_params: dict):
        scan_min = common_params['scan_min']
        scan_max = common_params['scan_max']

        gmax = compare_params['gmax']
        ln = compare_params['ln']
        psi_b = compare_params['psi_b']
        z = compare_params['z']
        d_lambda = compare_params['d_over_lambda']

        phi = np.linspace(scan_min, scan_max, 20_000)

        # Build each pattern's params from its own defaults, then overlay the
        # shared compare inputs. Starting from get_default_params() keeps the
        # compare path from drifting if a pattern adds or renames a parameter.
        ln672 = min([-20.0, -25.0], key=lambda value: abs(value - ln))
        plan = [
            (S1528Pattern(),
             {'model': '1.2 multiple-beam envelope', 'gmax': gmax,
              'd_over_lambda': d_lambda, 'z': z, 'psi_b': psi_b,
              'ln': f'{ln:g} dB'},
             f"S.1528  Gm={gmax:g} dBi, LN={ln:g} dB"),
            (S672Pattern(),
             {'gmax': gmax, 'psi_b': psi_b, 'z': z, 'ln': f'{ln672:g} dB'},
             f"S.672   Gm={gmax:g} dBi, LN={ln672:g} dB"
             + (f"  (snapped from {ln:g})" if ln672 != ln else "")),
            (S465Pattern(),
             {'d_over_lambda': d_lambda},
             f"S.465   D/lambda={d_lambda:g}"),
            (S580Pattern(),
             {'d_over_lambda': d_lambda},
             f"S.580   D/lambda={d_lambda:g}"),
        ]

        curves: list[tuple[str, np.ndarray]] = []
        try:
            for pattern, overrides, label in plan:
                params = pattern.get_default_params()
                params.update(overrides)
                curves.append((label, pattern.gain(phi, params)))
        except Exception as exc:
            QMessageBox.critical(self, "Comparison error",
                                 f"Could not evaluate comparison:\n{exc}")
            return

        self._contour_lines.clear()
        self._ax.clear()
        default_colors = list(_COMPARE_COLORS.values())
        for i, (label, G) in enumerate(curves):
            color = default_colors[i % len(default_colors)]
            self._ax.plot(phi, G, linewidth=1.5, color=color, label=label)

        finite_arrays = [G[np.isfinite(G)] for _, G in curves if np.any(np.isfinite(G))]
        all_finite = np.concatenate(finite_arrays) if finite_arrays else np.array([])
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
        self._ax.set_title("Current ITU-R Antenna Pattern Comparison")
        self._ax.grid(True, alpha=0.3)
        self._ax.legend(loc='upper right', fontsize=8)
        self._canvas.draw()

        mf = QFont("Courier New", 9)
        for row in range(len(DB_LEVELS)):
            self._table.setItem(row, 1, _cell("-", mf))
            self._table.setItem(row, 2, _cell("-", mf))
            self._table.setItem(row, 3, _cell("compare mode", mf))

    # --------------------------------------------------------------- contours

    def _toggle_contour_lines(self):
        """Immediately show or hide all stored contour lines without re-calculating."""
        visible = self._show_contours_cb.isChecked()
        for line in self._contour_lines:
            line.set_visible(visible)
        self._canvas.draw_idle()

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
        if not path:
            return
        if not path.lower().endswith('.png'):
            path += '.png'
        try:
            self._figure.savefig(path, dpi=150, bbox_inches='tight')
        except Exception as exc:
            QMessageBox.critical(self, "Save error",
                                 f"Could not save image:\n{exc}")


# ------------------------------------------------------------------ utilities

def _cell(text: str, font: QFont) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    item.setFont(font)
    return item
