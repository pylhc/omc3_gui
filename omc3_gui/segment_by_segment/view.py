
# from omc3_gui.segment_by_segment.segment_by_segment_ui import Ui_main_window
import logging
from pathlib import Path
from typing import Dict, List, Tuple

import pyqtgraph as pg
from accwidgets.graph import StaticPlotWidget
from accwidgets.graph.widgets.plotitem import ExViewBox
from qtpy import QtWidgets, uic
from qtpy.QtCore import Qt, Signal, Slot, QModelIndex

from omc3_gui.plotting.classes import DualPlot
from omc3_gui.segment_by_segment.model import Measurement, MeasurementListModel, SegmentTableModel
from omc3_gui.utils.base_classes import View
from omc3_gui.utils.counter import HorizontalGridLayoutFiller
from omc3_gui.utils.widgets import EditButton, OpenButton, RemoveButton, RunButton

LOGGER = logging.getLogger(__name__)

class Tab:
    PHASE: str = "Phase"


class SbSWindow(View):
    WINDOW_TITLE = "OMC Segment-by-Segment"

    sig_load_button_clicked = Signal()
    sig_remove_button_clicked = Signal()
    sig_matcher_button_clicked = Signal()
    sig_edit_measurement_button_clicked = Signal(Measurement)
    sig_list_optics_double_clicked = Signal(Measurement)

    _tabs: Dict[str, DualPlot]
    _tabs_widget: QtWidgets.QTabWidget
    _list_view_measurements: QtWidgets.QListView
    _table_segments: QtWidgets.QTableView

    # Buttons ---
    button_load: QtWidgets.QPushButton
    button_remove: QtWidgets.QPushButton
    button_edit: QtWidgets.QPushButton
    button_matcher: QtWidgets.QPushButton

    button_run_segment: QtWidgets.QPushButton
    button_remove_segment: QtWidgets.QPushButton
    button_copy_segment: QtWidgets.QPushButton
    button_new_segment: QtWidgets.QPushButton

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_gui()
        self.connect_signals()

        self.plot()

    def connect_signals(self):
        self.button_load.clicked.connect(self._handle_load_files_button_clicked)
        self._list_view_measurements.doubleClicked.connect(self._handle_list_measurements_double_clicked)

    @Slot()
    def _handle_load_files_button_clicked(self):
        LOGGER.debug("Loading Optics files button clicked.")
        self.sig_load_button_clicked.emit()

    @Slot(QModelIndex)
    def _handle_list_measurements_double_clicked(self, idx):
        LOGGER.debug(f"Entry in Optics List double-clicked: {idx.data(role=Qt.DisplayRole)}")


    def _build_gui(self):
        self.setWindowTitle(self.WINDOW_TITLE)
        self._central = QtWidgets.QSplitter(Qt.Horizontal)

        def build_navigation_widget():  # --- Left Hand Side 
            navigation_widget = QtWidgets.QSplitter(Qt.Vertical)

            def build_navigation_top():
                nav_top = QtWidgets.QWidget()

                layout = QtWidgets.QVBoxLayout()
                nav_top.setLayout(layout)
                layout.addWidget(QtWidgets.QLabel("Loaded Optics:"))

                self._list_view_measurements = QtWidgets.QListView()
                self._list_view_measurements.setModel(MeasurementListModel())
                self._list_view_measurements.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
                layout.addWidget(self._list_view_measurements)

                def build_measurement_buttons():
                    grid_buttons = QtWidgets.QGridLayout()
                    grid_buttons_filler = HorizontalGridLayoutFiller(layout=grid_buttons, cols=2)

                    load = OpenButton("Load")
                    grid_buttons_filler.add(load)
                    self.button_load = load

                    remove = RemoveButton()
                    grid_buttons_filler.add(remove)
                    self.button_remove = remove

                    edit = EditButton()
                    grid_buttons_filler.add(edit, col_span=2)
                    self.button_edit = edit

                    matcher = RunButton("Run Matcher")
                    grid_buttons_filler.add(matcher, col_span=2)
                    self.button_matcher = matcher
                
                    return grid_buttons

                layout.addLayout(build_measurement_buttons())
                return nav_top
            navigation_widget.addWidget(build_navigation_top())


            def build_navigation_bottom():
                nav_bottom = QtWidgets.QWidget()

                layout = QtWidgets.QVBoxLayout()
                nav_bottom.setLayout(layout)

                layout.addWidget(QtWidgets.QLabel("Segments:"))

                self._table_segments = QtWidgets.QTableView()
                layout.addWidget(self._table_segments)
                self._table_segments.setModel(SegmentTableModel())

                header = self._table_segments.horizontalHeader()
                header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)       
                header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)

                self._table_segments.setShowGrid(True)

                def build_segment_buttons():
                    grid_buttons = QtWidgets.QGridLayout()
                    grid_buttons_filler = HorizontalGridLayoutFiller(layout=grid_buttons, cols=3)

                    run = RunButton("Run Segment(s)")
                    grid_buttons_filler.add(run, col_span=3)
                    self.button_run_segment = run

                    new = OpenButton("New")
                    grid_buttons_filler.add(new)
                    self.button_new_segment = new
                    
                    copy = EditButton("Copy")
                    grid_buttons_filler.add(copy)
                    self.button_copy_segment = copy
                    
                    remove = RemoveButton("Remove")
                    grid_buttons_filler.add(remove)
                    self.button_remove_segment = remove
                
                    return grid_buttons
                layout.addLayout(build_segment_buttons())
                return nav_bottom

            navigation_widget.addWidget(build_navigation_bottom())
            return navigation_widget
        self._central.addWidget(build_navigation_widget())


        def build_tabs_widget():  # --- Right Hand Side
            self._tabs_widget = QtWidgets.QTabWidget()
            self._tabs = self._create_tabs(self._tabs_widget)
            return self._tabs_widget

        self._central.addWidget(build_tabs_widget())

        # Set up main widget layout ----
        self._central.setSizes([300, 1000])
        self._central.setStretchFactor(1, 3)
        
        self.setCentralWidget(self._central)
        
    
    def _create_tabs(self, tab_widget: QtWidgets.QTabWidget) -> Dict[str, "DualPlot"]:
        tabs = {}

        new_plot = DualPlot()
        tab_widget.addTab(new_plot, Tab.PHASE)
        tabs[Tab.PHASE] = new_plot

        return tabs


    def get_measurement_list(self) -> MeasurementListModel:
        return self._list_view_measurements.model()


    
    def plot(self):
        pass
        # for plot in self._tabs["Phase"].plots:
        #     data = pg.PlotDataItem([1,2,3], [4,5,6], data=["one", "two", "three"], name="Testing Line", symbol='o')
        #     data.scatter.opts['hoverable'] = True
        #     # data.sigPointsHovered.connect(self.hovered)
        #     # data.sigPointsClicked.connect(self.clicked)
        #     plot.addItem(data)

    
    def hovered(self, item, points, ev):
        print('hovered')
    
    def clicked(self, item, points, ev):
        print('clicked')


