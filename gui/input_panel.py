from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QHBoxLayout,
    QLabel, QDoubleSpinBox, QComboBox, QPushButton,
    QGroupBox, QScrollArea, QFrame,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont

from patterns import PATTERN_REGISTRY
from patterns.base import ParamSpec
from utils.aperture import d_lambda_from_gmax, psi_b_from_d_lambda


class InputPanel(QWidget):
    """Left-hand input panel."""

    calculate_requested = pyqtSignal(object, dict, dict)
    compare_requested = pyqtSignal(dict, dict)

    def __init__(self):
        super().__init__()
        self.setMinimumWidth(300)
        self.setMaximumWidth(420)
        self._param_widgets: dict = {}
        self._param_rows: dict = {}
        self._param_specs: dict = {}
        self._param_warning_labels: dict = {}
        self._setup_ui()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)

        title = QLabel("Antenna Pattern Tool")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(11)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        self._main_layout = QVBoxLayout(container)
        self._main_layout.setContentsMargins(2, 2, 2, 2)
        self._main_layout.setSpacing(6)
        scroll.setWidget(container)
        outer.addWidget(scroll, 1)

        grp_sel = QGroupBox("ITU-R Recommendation")
        form_sel = QFormLayout(grp_sel)
        self._pattern_combo = QComboBox()
        for pattern in PATTERN_REGISTRY:
            self._pattern_combo.addItem(f"{pattern.name}  ({pattern.station_type} station)")
        self._pattern_combo.currentIndexChanged.connect(self._rebuild_param_group)
        form_sel.addRow("Pattern:", self._pattern_combo)
        self._main_layout.addWidget(grp_sel)

        self._param_group = QGroupBox("Pattern Parameters")
        self._param_form = QFormLayout(self._param_group)
        self._main_layout.addWidget(self._param_group)

        grp_geo = QGroupBox("Scan Range & Geometry")
        form_geo = QFormLayout(grp_geo)
        self._scan_min = self._spin(-180.0, -180.0, 0.0, 1.0, 'deg', 1)
        self._scan_max = self._spin(180.0, 0.0, 180.0, 1.0, 'deg', 1)
        self._orbit_alt = self._spin(500.0, 100.0, 100_000.0, 50.0, 'km', 1)
        self._min_elev_angle = self._spin(10.0, 0.0, 90.0, 1.0, 'deg', 1)
        self._orbit_alt.setToolTip('Orbit altitude used to compute the boresight scan angle from nadir.')
        self._min_elev_angle.setToolTip(
            'Minimum ground elevation angle. This is converted to the boresight scan angle from nadir.'
        )
        form_geo.addRow("Scan Min:", self._scan_min)
        form_geo.addRow("Scan Max:", self._scan_max)
        form_geo.addRow("Orbit Altitude:", self._orbit_alt)
        form_geo.addRow("Minimum Elevation Angle:", self._min_elev_angle)
        self._main_layout.addWidget(grp_geo)

        grp_cmp = QGroupBox("Compare Current Patterns")
        form_cmp = QFormLayout(grp_cmp)
        form_cmp.setSpacing(4)

        self._cmp_gmax = self._spin(32.3, 0.0, 65.0, 0.1, 'dBi', 1)
        self._cmp_eta = self._spin(0.60, 0.05, 1.00, 0.01, '', 2)
        self._cmp_ln = QComboBox()
        for value in ['-20 dB', '-25 dB']:
            self._cmp_ln.addItem(value)
        self._cmp_ln.setCurrentText('-25 dB')
        self._cmp_ln.setToolTip('LN for S.1528 and S.672 current single-feed envelopes.')
        self._cmp_psi_b = self._spin(1.0, 0.001, 90.0, 0.01, 'deg', 3)
        self._cmp_z = self._spin(1.0, 1.0, 5.0, 0.01, '', 2)
        # Floor matches the per-pattern S.465 form (down to 1.0) so small dishes
        # can be compared, not just large ones.
        self._cmp_d_lambda = self._spin(100.0, 1.0, 10000.0, 1.0, '', 1)

        form_cmp.addRow("Peak Gain (Gmax):", self._cmp_gmax)
        form_cmp.addRow("Aperture Efficiency:", self._cmp_eta)
        form_cmp.addRow("LN (space patterns):", self._cmp_ln)
        form_cmp.addRow("3 dB half-beamwidth:", self._with_calc_button(
            self._cmp_psi_b,
            self._calc_compare_psi_b,
            "Estimate from D/lambda",
        ))
        form_cmp.addRow("Beam axis ratio z:", self._cmp_z)
        form_cmp.addRow("D/lambda:", self._with_calc_button(
            self._cmp_d_lambda,
            self._calc_compare_d_lambda,
            "Estimate from peak gain and aperture efficiency",
        ))

        cmp_btn = QPushButton("Plot Comparison")
        cmp_font = QFont()
        cmp_font.setBold(True)
        cmp_btn.setFont(cmp_font)
        cmp_btn.setMinimumHeight(30)
        cmp_btn.clicked.connect(self._on_compare)
        form_cmp.addRow(cmp_btn)
        self._main_layout.addWidget(grp_cmp)

        self._main_layout.addStretch()

        calc_btn = QPushButton("Calculate & Plot")
        calc_btn.setMinimumHeight(38)
        calc_font = QFont()
        calc_font.setBold(True)
        calc_btn.setFont(calc_font)
        calc_btn.clicked.connect(self._on_calculate)
        outer.addWidget(calc_btn)

        self._rebuild_param_group(0)

    @staticmethod
    def _spin(value, lo, hi, step, units='', decimals=3) -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setRange(lo, hi)
        widget.setValue(value)
        widget.setSingleStep(step)
        widget.setDecimals(decimals)
        if units:
            widget.setSuffix(f'  {units}')
        return widget

    @staticmethod
    def _with_calc_button(widget: QWidget, callback, tooltip: str) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(widget, 1)
        btn = QPushButton("Calc")
        btn.setMaximumWidth(42)
        btn.setToolTip(tooltip)
        btn.clicked.connect(callback)
        row_layout.addWidget(btn)
        return row

    def _rebuild_param_group(self, index: int):
        while self._param_form.rowCount():
            self._param_form.removeRow(0)
        self._param_widgets.clear()
        self._param_rows.clear()
        self._param_specs.clear()
        self._param_warning_labels.clear()

        pattern = PATTERN_REGISTRY[index]
        self._param_group.setTitle(f"{pattern.name} Parameters")

        for spec in pattern.get_params_spec():
            widget = self._make_widget(spec)
            if widget is None:
                continue

            label = f"{spec.label}:"
            if spec.units:
                label = f"{spec.label} ({spec.units}):"
            label_widget = QLabel(label)

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
                field_core = row
            else:
                field_core = widget

            warning = QLabel("")
            warning.setWordWrap(True)
            warning.setStyleSheet("color: #9a5a00; font-size: 10px;")
            warning.setVisible(False)

            field_widget = QWidget()
            field_layout = QVBoxLayout(field_widget)
            field_layout.setContentsMargins(0, 0, 0, 0)
            field_layout.setSpacing(2)
            field_layout.addWidget(field_core)
            field_layout.addWidget(warning)

            self._param_form.addRow(label_widget, field_widget)

            self._param_widgets[spec.name] = widget
            self._param_rows[spec.name] = (label_widget, field_widget)
            self._param_specs[spec.name] = spec
            self._param_warning_labels[spec.name] = warning
            self._connect_param_refresh(widget)

        self._refresh_param_applicability()

    def _make_widget(self, spec: ParamSpec):
        if spec.type == 'float':
            widget = QDoubleSpinBox()
            widget.setRange(
                spec.min if spec.min is not None else -1e6,
                spec.max if spec.max is not None else 1e6,
            )
            widget.setValue(float(spec.default))
            widget.setSingleStep(spec.step if spec.step else 0.1)
            widget.setDecimals(3)
            if spec.tooltip:
                widget.setToolTip(spec.tooltip)
            return widget

        if spec.type == 'choice':
            widget = QComboBox()
            for choice in spec.choices or []:
                widget.addItem(str(choice))
            widget.setCurrentText(str(spec.default))
            if spec.tooltip:
                widget.setToolTip(spec.tooltip)
            return widget

        return None

    def _connect_param_refresh(self, widget):
        if isinstance(widget, QDoubleSpinBox):
            widget.valueChanged.connect(lambda _value: self._refresh_param_applicability())
        elif isinstance(widget, QComboBox):
            widget.currentTextChanged.connect(lambda _value: self._refresh_param_applicability())

    def _refresh_param_applicability(self):
        pattern = PATTERN_REGISTRY[self._pattern_combo.currentIndex()]
        params = self._collect_pattern_params()
        for name, spec in self._param_specs.items():
            active = pattern.is_param_applicable(name, params)
            label_widget, field_widget = self._param_rows[name]
            label_widget.setEnabled(active)
            field_widget.setEnabled(active)

            warning_label = self._param_warning_labels[name]
            if active:
                warning = pattern.param_warning(name, params)
            else:
                warning = "Not used by the selected reference pattern."
            warning_label.setText(warning)
            warning_label.setVisible(bool(warning))

    def _auto_compute(self, spec: ParamSpec, widget: QDoubleSpinBox):
        pattern = PATTERN_REGISTRY[self._pattern_combo.currentIndex()]
        params = self._collect_pattern_params()
        value = pattern.suggest_derived(spec.name, params)
        if value is not None:
            widget.setValue(value)
        self._refresh_param_applicability()

    def _collect_pattern_params(self) -> dict:
        pattern = PATTERN_REGISTRY[self._pattern_combo.currentIndex()]
        result = {}
        for spec in pattern.get_params_spec():
            widget = self._param_widgets.get(spec.name)
            if widget is None:
                result[spec.name] = spec.default
            elif isinstance(widget, QDoubleSpinBox):
                result[spec.name] = widget.value()
            elif isinstance(widget, QComboBox):
                result[spec.name] = widget.currentText()
        return result

    def _common_params(self) -> dict:
        return {
            'scan_min': self._scan_min.value(),
            'scan_max': self._scan_max.value(),
            'orbit_alt': self._orbit_alt.value(),
            'min_elev_angle': self._min_elev_angle.value(),
        }

    def _on_calculate(self):
        pattern = PATTERN_REGISTRY[self._pattern_combo.currentIndex()]
        self.calculate_requested.emit(
            pattern,
            self._collect_pattern_params(),
            self._common_params(),
        )

    def _calc_compare_d_lambda(self):
        d_lambda = d_lambda_from_gmax(self._cmp_gmax.value(), self._cmp_eta.value())
        self._cmp_d_lambda.setValue(d_lambda)

    def _calc_compare_psi_b(self):
        self._cmp_psi_b.setValue(psi_b_from_d_lambda(self._cmp_d_lambda.value()))

    def _on_compare(self):
        ln_value = float(self._cmp_ln.currentText().replace(' dB', ''))
        compare_params = {
            'gmax': self._cmp_gmax.value(),
            'ln': ln_value,
            'psi_b': self._cmp_psi_b.value(),
            'z': self._cmp_z.value(),
            'd_over_lambda': self._cmp_d_lambda.value(),
        }
        self.compare_requested.emit(compare_params, self._common_params())
