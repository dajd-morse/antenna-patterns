from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QHBoxLayout,
    QLabel, QDoubleSpinBox, QComboBox, QPushButton,
    QGroupBox, QScrollArea, QFrame, QCheckBox,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont

from patterns import PATTERN_REGISTRY
from patterns.base import ParamSpec


class InputPanel(QWidget):
    """Left-hand input panel."""

    calculate_requested = pyqtSignal(object, dict, dict)   # pattern, pattern_params, common_params
    compare_requested   = pyqtSignal(dict,        dict)    # compare_params,           common_params

    def __init__(self):
        super().__init__()
        self.setMinimumWidth(300)
        self.setMaximumWidth(420)
        self._param_widgets: dict = {}
        self._setup_ui()

    # ------------------------------------------------------------------ layout

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)

        title = QLabel("Antenna Pattern Tool")
        f = QFont(); f.setBold(True); f.setPointSize(11)
        title.setFont(f)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(title)

        # scrollable parameter area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        self._main_layout = QVBoxLayout(container)
        self._main_layout.setContentsMargins(2, 2, 2, 2)
        self._main_layout.setSpacing(6)
        scroll.setWidget(container)
        outer.addWidget(scroll, 1)

        # ── pattern selector ─────────────────────────────────────────────────
        grp_sel = QGroupBox("ITU-R Recommendation")
        form_sel = QFormLayout(grp_sel)
        self._pattern_combo = QComboBox()
        for p in PATTERN_REGISTRY:
            self._pattern_combo.addItem(p.name)
        self._pattern_combo.currentIndexChanged.connect(self._rebuild_param_group)
        form_sel.addRow("Pattern:", self._pattern_combo)
        self._main_layout.addWidget(grp_sel)

        # ── dynamic pattern parameters ────────────────────────────────────────
        self._param_group = QGroupBox("Pattern Parameters")
        self._param_form  = QFormLayout(self._param_group)
        self._main_layout.addWidget(self._param_group)

        # ── common geometry ───────────────────────────────────────────────────
        grp_geo = QGroupBox("Scan Range & Geometry")
        form_geo = QFormLayout(grp_geo)

        self._scan_min   = self._spin(-180.0, -180.0,  0.0, 1.0, '°', 1)
        self._scan_max   = self._spin( 180.0,    0.0,180.0, 1.0, '°', 1)
        self._orbit_alt  = self._spin( 500.0,  100.0, 100_000.0, 50.0, 'km', 1)
        self._elev_angle = self._spin(  90.0,    0.0,  90.0, 1.0, '°', 1)

        form_geo.addRow("Scan Min:",        self._scan_min)
        form_geo.addRow("Scan Max:",        self._scan_max)
        form_geo.addRow("Orbit Altitude:",  self._orbit_alt)
        form_geo.addRow("Elevation Angle:", self._elev_angle)
        self._main_layout.addWidget(grp_geo)

        # ── compare all patterns ─────────────────────────────────────────────
        grp_cmp = QGroupBox("Compare All Patterns")
        form_cmp = QFormLayout(grp_cmp)
        form_cmp.setSpacing(4)

        self._cmp_gmax  = self._spin(32.3,  0.0,  65.0, 0.1, 'dBi', 1)
        self._cmp_ls    = QComboBox()
        for v in ['-20 dB', '-25 dB', '-30 dB']:
            self._cmp_ls.addItem(v)
        self._cmp_ls.setCurrentText('-25 dB')
        self._cmp_ls.setToolTip(
            'Ls for both S.1528 and S.672. S.672 only accepts −20, −25, or −30 dB.'
        )
        self._cmp_psib  = self._spin(1.0, 0.001, 90.0, 0.01, 'deg', 3)
        self._cmp_psi0  = self._spin(1.0, 0.001, 90.0, 0.01, 'deg', 3)
        self._cmp_dλ    = self._spin(100.0, 50.0, 10000.0, 1.0, '', 1)
        self._cmp_legacy = QCheckBox("Include legacy/pre-1993 variants")
        self._cmp_legacy.setToolTip(
            'Also plot pre-1993 S.465 and pre-1995 S.580 variants'
        )

        form_cmp.addRow("Peak Gain (Gmax):",        self._cmp_gmax)
        form_cmp.addRow("Ls (S.1528 & S.672):",     self._cmp_ls)
        form_cmp.addRow("ψb — S.1528 beamwidth:",   self._cmp_psib)
        form_cmp.addRow("ψ₀ — S.672 beamwidth:",    self._cmp_psi0)
        form_cmp.addRow("D/λ (S.465 & S.580):",     self._cmp_dλ)
        form_cmp.addRow("",                          self._cmp_legacy)

        cmp_btn = QPushButton("Plot Comparison")
        f2 = QFont(); f2.setBold(True)
        cmp_btn.setFont(f2)
        cmp_btn.setMinimumHeight(30)
        cmp_btn.clicked.connect(self._on_compare)
        form_cmp.addRow(cmp_btn)
        self._main_layout.addWidget(grp_cmp)

        self._main_layout.addStretch()

        # ── calculate button (outside scroll) ────────────────────────────────
        calc_btn = QPushButton("Calculate & Plot")
        calc_btn.setMinimumHeight(38)
        f3 = QFont(); f3.setBold(True)
        calc_btn.setFont(f3)
        calc_btn.clicked.connect(self._on_calculate)
        outer.addWidget(calc_btn)

        self._rebuild_param_group(0)

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _spin(value, lo, hi, step, units='', decimals=3) -> QDoubleSpinBox:
        w = QDoubleSpinBox()
        w.setRange(lo, hi)
        w.setValue(value)
        w.setSingleStep(step)
        w.setDecimals(decimals)
        if units:
            w.setSuffix(f'  {units}')
        return w

    # --------------------------------------------------------- dynamic params

    def _rebuild_param_group(self, index: int):
        while self._param_form.rowCount():
            self._param_form.removeRow(0)
        self._param_widgets.clear()

        pattern = PATTERN_REGISTRY[index]
        self._param_group.setTitle(f"{pattern.name} Parameters")

        for spec in pattern.get_params_spec():
            widget = self._make_widget(spec)
            if widget is None:
                continue

            label = f"{spec.label}:"
            if spec.units:
                label = f"{spec.label} ({spec.units}):"

            if spec.computed:
                row = QWidget()
                rl = QHBoxLayout(row)
                rl.setContentsMargins(0, 0, 0, 0)
                rl.addWidget(widget, 1)
                btn = QPushButton("Calc")
                btn.setMaximumWidth(42)
                btn.setToolTip(f"Auto-compute {spec.label} from current parameters")
                btn.clicked.connect(
                    lambda _chk, s=spec, w=widget: self._auto_compute(s, w)
                )
                rl.addWidget(btn)
                self._param_form.addRow(label, row)
            else:
                self._param_form.addRow(label, widget)

            self._param_widgets[spec.name] = widget

    def _make_widget(self, spec: ParamSpec):
        if spec.type == 'float':
            w = QDoubleSpinBox()
            w.setRange(
                spec.min if spec.min is not None else -1e6,
                spec.max if spec.max is not None else  1e6,
            )
            w.setValue(float(spec.default))
            w.setSingleStep(spec.step if spec.step else 0.1)
            w.setDecimals(3)
            if spec.tooltip:
                w.setToolTip(spec.tooltip)
            return w

        if spec.type == 'choice':
            w = QComboBox()
            for c in (spec.choices or []):
                w.addItem(str(c))
            w.setCurrentText(str(spec.default))
            if spec.tooltip:
                w.setToolTip(spec.tooltip)
            return w

        return None

    def _auto_compute(self, spec: ParamSpec, widget: QDoubleSpinBox):
        pattern = PATTERN_REGISTRY[self._pattern_combo.currentIndex()]
        params  = self._collect_pattern_params()
        value   = pattern.suggest_derived(spec.name, params)
        if value is not None:
            widget.setValue(value)

    # ------------------------------------------------------- param collection

    def _collect_pattern_params(self) -> dict:
        pattern = PATTERN_REGISTRY[self._pattern_combo.currentIndex()]
        result  = {}
        for spec in pattern.get_params_spec():
            w = self._param_widgets.get(spec.name)
            if w is None:
                result[spec.name] = spec.default
            elif isinstance(w, QDoubleSpinBox):
                result[spec.name] = w.value()
            elif isinstance(w, QComboBox):
                result[spec.name] = w.currentText()
        return result

    def _common_params(self) -> dict:
        return {
            'scan_min':   self._scan_min.value(),
            'scan_max':   self._scan_max.value(),
            'orbit_alt':  self._orbit_alt.value(),
            'elev_angle': self._elev_angle.value(),
        }

    # --------------------------------------------------------------- signals

    def _on_calculate(self):
        pattern = PATTERN_REGISTRY[self._pattern_combo.currentIndex()]
        self.calculate_requested.emit(
            pattern,
            self._collect_pattern_params(),
            self._common_params(),
        )

    def _on_compare(self):
        ls_str = self._cmp_ls.currentText()          # e.g. '-25 dB'
        ls_val = float(ls_str.replace(' dB', ''))    # e.g. -25.0
        compare_params = {
            'gmax':           self._cmp_gmax.value(),
            'ls':             ls_val,
            'psi_b':          self._cmp_psib.value(),
            'psi0':           self._cmp_psi0.value(),
            'd_over_lambda':  self._cmp_dλ.value(),
            'include_legacy': self._cmp_legacy.isChecked(),
        }
        self.compare_requested.emit(compare_params, self._common_params())
