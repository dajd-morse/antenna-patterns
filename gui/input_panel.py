from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QHBoxLayout,
    QLabel, QDoubleSpinBox, QComboBox, QPushButton,
    QGroupBox, QScrollArea, QFrame, QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont

from patterns import PATTERN_REGISTRY
from patterns.base import ParamSpec


class InputPanel(QWidget):
    """Left-hand input panel. Emits calculate_requested with (pattern, params, common)."""

    calculate_requested = pyqtSignal(object, dict, dict)

    def __init__(self):
        super().__init__()
        self.setMinimumWidth(290)
        self.setMaximumWidth(400)
        self._param_widgets: dict = {}
        self._setup_ui()

    # ------------------------------------------------------------------ layout

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)

        title = QLabel("Antenna Pattern Tool")
        f = QFont()
        f.setBold(True)
        f.setPointSize(11)
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

        # ---- pattern selector
        grp_sel = QGroupBox("ITU-R Recommendation")
        form_sel = QFormLayout(grp_sel)
        self._pattern_combo = QComboBox()
        for p in PATTERN_REGISTRY:
            self._pattern_combo.addItem(p.name)
        self._pattern_combo.currentIndexChanged.connect(self._rebuild_param_group)
        form_sel.addRow("Pattern:", self._pattern_combo)
        self._main_layout.addWidget(grp_sel)

        # ---- dynamic pattern parameters (rebuilt on pattern change)
        self._param_group = QGroupBox("Pattern Parameters")
        self._param_form = QFormLayout(self._param_group)
        self._main_layout.addWidget(self._param_group)

        # ---- common geometry inputs
        grp_geo = QGroupBox("Scan Range & Geometry")
        form_geo = QFormLayout(grp_geo)

        self._scan_min = self._spin(-180.0, -180.0, 0.0, 1.0, '°', 1)
        self._scan_max = self._spin(180.0, 0.0, 180.0, 1.0, '°', 1)
        form_geo.addRow("Scan Min:", self._scan_min)
        form_geo.addRow("Scan Max:", self._scan_max)

        self._orbit_alt = self._spin(500.0, 100.0, 100_000.0, 50.0, 'km', 1)
        form_geo.addRow("Orbit Altitude:", self._orbit_alt)

        self._elev_angle = self._spin(90.0, 0.0, 90.0, 1.0, '°', 1)
        form_geo.addRow("Elevation Angle:", self._elev_angle)

        self._main_layout.addWidget(grp_geo)
        self._main_layout.addStretch()

        # ---- calculate button (outside scroll area)
        calc_btn = QPushButton("Calculate & Plot")
        calc_btn.setMinimumHeight(38)
        f2 = QFont()
        f2.setBold(True)
        calc_btn.setFont(f2)
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

            label_text = f"{spec.label}:"
            if spec.units:
                label_text = f"{spec.label} ({spec.units}):"

            if spec.computed:
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.addWidget(widget, 1)
                btn = QPushButton("Calc")
                btn.setMaximumWidth(42)
                btn.setToolTip(f"Auto-compute {spec.label} from current parameters")
                btn.clicked.connect(
                    lambda _checked, s=spec, w=widget: self._auto_compute(s, w)
                )
                row_layout.addWidget(btn)
                self._param_form.addRow(label_text, row)
            else:
                self._param_form.addRow(label_text, widget)

            self._param_widgets[spec.name] = widget

    def _make_widget(self, spec: ParamSpec):
        if spec.type == 'float':
            w = QDoubleSpinBox()
            w.setRange(
                spec.min if spec.min is not None else -1e6,
                spec.max if spec.max is not None else 1e6,
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
        params = self._collect_pattern_params()
        value = pattern.suggest_derived(spec.name, params)
        if value is not None:
            widget.setValue(value)

    # ------------------------------------------------------- param collection

    def _collect_pattern_params(self) -> dict:
        pattern = PATTERN_REGISTRY[self._pattern_combo.currentIndex()]
        result = {}
        for spec in pattern.get_params_spec():
            w = self._param_widgets.get(spec.name)
            if w is None:
                result[spec.name] = spec.default
            elif isinstance(w, QDoubleSpinBox):
                result[spec.name] = w.value()
            elif isinstance(w, QComboBox):
                result[spec.name] = w.currentText()
        return result

    def _on_calculate(self):
        pattern = PATTERN_REGISTRY[self._pattern_combo.currentIndex()]
        pattern_params = self._collect_pattern_params()
        common_params = {
            'scan_min': self._scan_min.value(),
            'scan_max': self._scan_max.value(),
            'orbit_alt': self._orbit_alt.value(),
            'elev_angle': self._elev_angle.value(),
        }
        self.calculate_requested.emit(pattern, pattern_params, common_params)
