from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QSplitter
from PyQt6.QtCore import Qt

from gui.input_panel import InputPanel
from gui.plot_widget import PlotWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ITU-R Antenna Pattern Tool")
        self.resize(1440, 820)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.input_panel = InputPanel()
        self.plot_widget = PlotWidget()

        splitter.addWidget(self.input_panel)
        splitter.addWidget(self.plot_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 1100])

        layout.addWidget(splitter)

        self.input_panel.calculate_requested.connect(self.plot_widget.update_plot)
        self.input_panel.compare_requested.connect(self.plot_widget.compare_plot)
