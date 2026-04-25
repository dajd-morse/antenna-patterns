import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QGroupBox,
    QLabel, QDoubleSpinBox, QPushButton,
    QFileDialog, QHeaderView, QAbstractItemView,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from utils.geometry import nadir_angle_from_elevation

DB_LEVELS = [2, 4, 6, 8, 10, 15, 20]


class PlotWidget(QWidget):
    """Right-hand pane: plot + results table."""

    def __init__(self):
        super().__init__()
        self._last_phi: np.ndarray | None = None
        self._last_G: np.ndarray | None = None
        self._setup_ui()

    # ------------------------------------------------------------------ layout

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # ── top: plot ────────────────────────────────────────────────────────
        plot_container = QWidget()
        plot_layout = QVBoxLayout(plot_container)
        plot_layout.setContentsMargins(0, 0, 0, 0)

        self._figure = Figure(figsize=(10, 5), tight_layout=True)
        self._canvas = FigureCanvas(self._figure)
        self._ax = self._figure.add_subplot(111)
        self._toolbar = NavigationToolbar(self._canvas, self)

        # axis range controls
        ctrl = QWidget()
        ctrl_layout = QHBoxLayout(ctrl)
        ctrl_layout.setContentsMargins(4, 0, 4, 0)

        def _lbl(txt):
            return QLabel(txt)

        self._xmin_spin = self._axis_spin(-180, -180, 180, '°')
        self._xmax_spin = self._axis_spin(180, -180, 180, '°')
        self._ymin_spin = self._axis_spin(-20, -120, 100, 'dBi')
        self._ymax_spin = self._axis_spin(40, -120, 100, 'dBi')

        for lbl, w in [
            ("X min:", self._xmin_spin), ("X max:", self._xmax_spin),
            ("Y min:", self._ymin_spin), ("Y max:", self._ymax_spin),
        ]:
            ctrl_layout.addWidget(_lbl(lbl))
            ctrl_layout.addWidget(w)

        apply_btn = QPushButton("Apply Axes")
        apply_btn.clicked.connect(self._apply_axes)
        ctrl_layout.addWidget(apply_btn)

        save_btn = QPushButton("Save PNG…")
        save_btn.clicked.connect(self._save_png)
        ctrl_layout.addWidget(save_btn)
        ctrl_layout.addStretch()

        plot_layout.addWidget(self._toolbar)
        plot_layout.addWidget(self._canvas, 1)
        plot_layout.addWidget(ctrl)

        # ── bottom: results table ─────────────────────────────────────────────
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

        f = QFont("Courier New", 9)
        for row, db in enumerate(DB_LEVELS):
            item = QTableWidgetItem(f"−{db:2d} dB")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setFont(f)
            self._table.setItem(row, 0, item)

        results_layout.addWidget(self._table)

        splitter.addWidget(plot_container)
        splitter.addWidget(results_grp)
        splitter.setSizes([560, 200])
        layout.addWidget(splitter)

    @staticmethod
    def _axis_spin(value, lo, hi, units):
        w = QDoubleSpinBox()
        w.setRange(lo, hi)
        w.setValue(value)
        w.setSingleStep(1.0)
        w.setDecimals(1)
        w.setSuffix(f'  {units}')
        w.setMaximumWidth(110)
        return w

    # ------------------------------------------------------------------ slots

    def update_plot(self, pattern, pattern_params: dict, common_params: dict):
        scan_min = common_params['scan_min']
        scan_max = common_params['scan_max']
        orbit_alt = common_params['orbit_alt']
        elev_angle = common_params['elev_angle']

        phi = np.linspace(scan_min, scan_max, 20_000)
        G = pattern.gain(phi, pattern_params)

        self._last_phi = phi
        self._last_G = G

        gmax = float(pattern_params.get('gmax', np.nanmax(G)))

        # sync axis range spinners to scan range then auto-set Y
        self._xmin_spin.setValue(scan_min)
        self._xmax_spin.setValue(scan_max)
        self._ymin_spin.setValue(-20.0)
        self._ymax_spin.setValue(round(gmax + 5.0, 1))

        self._ax.clear()
        self._ax.plot(phi, G, color='steelblue', linewidth=1.5, label=pattern.name)
        self._ax.axhline(y=gmax, color='gray', linewidth=0.6, linestyle='--', alpha=0.5)

        # mark dB contour lines (positive-phi side)
        phi_pos = phi[phi >= 0]
        G_pos = G[phi >= 0]
        colors = ['#e06c00', '#c00000', '#800080', '#006600',
                  '#0055aa', '#aa0055', '#005555']
        theta_nadir = nadir_angle_from_elevation(elev_angle, orbit_alt)

        f = QFont("Courier New", 9)
        for row, (db, color) in enumerate(zip(DB_LEVELS, colors)):
            target = gmax - db
            angle = _first_descent(phi_pos, G_pos, target)
            if angle is not None:
                self._ax.axvline(x=angle, color=color, linewidth=0.8,
                                 linestyle=':', alpha=0.7)
                self._ax.axvline(x=-angle, color=color, linewidth=0.8,
                                 linestyle=':', alpha=0.7)
                nadir_scan = theta_nadir + angle
                note = ""
                self._table.setItem(row, 1, _cell(f"{angle:.3f}", f))
                self._table.setItem(row, 2, _cell(f"{nadir_scan:.3f}", f))
                self._table.setItem(row, 3, _cell(note, f))
            else:
                self._table.setItem(row, 1, _cell("N/A", f))
                self._table.setItem(row, 2, _cell("N/A", f))
                self._table.setItem(row, 3, _cell("beyond scan range", f))

        self._ax.set_xlabel("Angle from Boresight (degrees)")
        self._ax.set_ylabel("Gain (dBi)")
        self._ax.set_title(f"{pattern.name} — Antenna Gain Pattern")
        self._ax.set_xlim(scan_min, scan_max)
        self._ax.set_ylim(-20.0, gmax + 5.0)
        self._ax.grid(True, alpha=0.3)
        self._ax.legend(loc='upper right', fontsize=9)
        self._canvas.draw()

    def _apply_axes(self):
        if self._last_phi is None:
            return
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
    Return the first angle (from boresight) at which G descends through target.
    Uses linear interpolation between samples.
    """
    for i in range(len(G) - 1):
        if G[i] >= target > G[i + 1]:
            if G[i + 1] != G[i]:
                t = (target - G[i]) / (G[i + 1] - G[i])
                return float(phi[i] + t * (phi[i + 1] - phi[i]))
    return None


def _cell(text: str, font: QFont) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    item.setFont(font)
    return item
