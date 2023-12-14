
# from omc3_gui.segment_by_segment.segment_by_segment_ui import Ui_main_window
import logging
from typing import Dict, Iterator, List, Sequence, Tuple

from PyQt5 import QtGui
from qtpy import QtGui, QtWidgets
from qtpy.QtCore import QItemSelectionModel, QModelIndex, Qt, Signal, Slot, QEvent

from omc3_gui.plotting.classes import DualPlot
from omc3_gui.segment_by_segment.main_model import MeasurementListModel, SegmentTableModel
from omc3_gui.segment_by_segment.measurement_model import OpticsMeasurement
from omc3_gui.segment_by_segment.segment_model import SegmentItemModel
from omc3_gui.utils import colors
from omc3_gui.utils.ui_base_classes import View
from omc3_gui.utils.counter import HorizontalGridLayoutFiller
from omc3_gui.utils.styles import MONOSPACED_TOOLTIP
from omc3_gui.utils.widgets import (DefaultButton, EditButton, OpenButton, RemoveButton, RunButton)
from omc3.definitions.optics import ColumnsAndLabels, PHASE_COLUMN
from omc3_gui.utils.iteration_classes import IterClass 

LOGGER = logging.getLogger(__name__)

class Tabs(IterClass):
    PHASE: ColumnsAndLabels = PHASE_COLUMN


class SbSWindow(View):
    WINDOW_TITLE = "OMC Segment-by-Segment"

    # QtSignals need to be defined as class-attributes
    sig_list_optics_double_clicked = Signal(OpticsMeasurement)
    sig_list_optics_selected = Signal(tuple)  # Tuple[OpticsMeasurement]
    sig_table_segments_selected = Signal(tuple)
    sig_thread_spinner_double_clicked = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setStatusBar(self.statusBar())
        
        # List of UI elements accessible as instance-attributes:
        # Widgets ---
        self._cental: QtWidgets.QSplitter = None
        self._tabs_widget: QtWidgets.QTabWidget = None
        self._list_view_measurements: QtWidgets.QListView = None
        self._table_segments: QtWidgets.QTableView = None

        # Buttons ---
        self.button_load_measurement: QtWidgets.QPushButton = None
        self.button_remove_measurement: QtWidgets.QPushButton = None
        self.button_edit_measurement: QtWidgets.QPushButton = None
        self.button_edit_corrections: QtWidgets.QPushButton = None
        self.button_run_matcher: QtWidgets.QPushButton = None

        self.button_run_segment: QtWidgets.QPushButton = None
        self.button_remove_segment: QtWidgets.QPushButton = None
        self.button_copy_segment: QtWidgets.QPushButton = None
        self.button_new_segment: QtWidgets.QPushButton = None
        self.button_default_segments: QtWidgets.QPushButton = None
        self.button_load_segments: QtWidgets.QPushButton = None
        
        self._build_gui()
        self._connect_signals()

        self.plot()

    def _connect_signals(self):
        # Optics Measurements ---
        self._list_view_measurements.doubleClicked.connect(self._handle_list_measurements_double_clicked)
        self._list_view_measurements.selectionModel().selectionChanged.connect(self._handle_list_measurements_selected)

        # Segments ---
        # Set in set_segments, as this needs to be reset after each model setting.

    # Slots --------------------------------------------------------------------
    @Slot(QModelIndex)
    def _handle_list_measurements_double_clicked(self, idx):
        LOGGER.debug(f"Entry in Optics List double-clicked: {idx.data(role=Qt.DisplayRole)}")
        self.sig_list_optics_double_clicked.emit(idx.data(role=Qt.EditRole))

    @Slot()
    def _handle_list_measurements_selected(self):        
        LOGGER.debug("Optics List selection changed.")
        selected_measurements = self.get_selected_measurements()
        self.sig_list_optics_selected.emit(selected_measurements)

    @Slot()
    def _handle_table_segments_selected(self):
        LOGGER.debug("Segment Table selection changed.")
        selected_segments = self.get_selected_segments()
        self.sig_table_segments_selected.emit(selected_segments)

    # GUI-Elements -------------------------------------------------------------
    def _build_gui(self):
        self._central = QtWidgets.QSplitter(Qt.Horizontal)

        def build_navigation_widget():  # --- Left Hand Side 
            navigation_widget = QtWidgets.QSplitter(Qt.Vertical)

            def build_navigation_top():
                nav_top = QtWidgets.QWidget()

                layout = QtWidgets.QVBoxLayout()
                nav_top.setLayout(layout)
                layout.addWidget(QtWidgets.QLabel("Loaded Optics:"))

                self._list_view_measurements = MeasurementListView()
                layout.addWidget(self._list_view_measurements)

                def build_measurement_buttons():
                    grid_buttons = QtWidgets.QGridLayout()
                    grid_buttons_filler = HorizontalGridLayoutFiller(layout=grid_buttons, cols=3)

                    load = OpenButton("Load")
                    grid_buttons_filler.add(load)
                    self.button_load_measurement = load
                    
                    edit = EditButton()
                    grid_buttons_filler.add(edit)
                    self.button_edit_measurement = edit

                    remove = RemoveButton()
                    grid_buttons_filler.add(remove)
                    self.button_remove_measurement = remove

                    matcher = RunButton("Run Matcher")
                    grid_buttons_filler.add(matcher, col_span=2)
                    self.button_run_matcher = matcher
                    
                    edit_corrections = DefaultButton("Corrections")
                    grid_buttons_filler.add(edit_corrections)
                    self.button_edit_corrections = edit_corrections
                
                    return grid_buttons

                layout.addLayout(build_measurement_buttons())
                return nav_top
            navigation_widget.addWidget(build_navigation_top())


            def build_navigation_bottom():
                nav_bottom = QtWidgets.QWidget()

                layout = QtWidgets.QVBoxLayout()
                nav_bottom.setLayout(layout)

                layout.addWidget(QtWidgets.QLabel("Segments:"))

                self._table_segments = SegmentTableView()
                layout.addWidget(self._table_segments)

                def build_segment_buttons():
                    grid_buttons = QtWidgets.QGridLayout()
                    grid_buttons_filler = HorizontalGridLayoutFiller(layout=grid_buttons, cols=3)

                    run = RunButton("Run Segment(s)")
                    grid_buttons_filler.add(run, col_span=3)
                    self.button_run_segment = run

                    new = DefaultButton("New")
                    grid_buttons_filler.add(new)
                    self.button_new_segment = new
                    
                    default = DefaultButton("Add Defaults")
                    grid_buttons_filler.add(default)
                    self.button_default_segments = default

                    load = OpenButton("Load")
                    grid_buttons_filler.add(load)
                    self.button_load_segments = load


                    copy = EditButton("Copy")
                    grid_buttons_filler.add(copy)
                    self.button_copy_segment = copy

                    grid_buttons_filler.add(QtWidgets.QWidget())
                    
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
            for tab in Tabs.values():
                self._tabs_widget.addTab(DualPlot(), tab.text_label.capitalize())
            return self._tabs_widget

        self._central.addWidget(build_tabs_widget())

        # Set up main widget layout ----
        self._central.setSizes([300, 1000])
        self._central.setStretchFactor(1, 3)
        
        self.setCentralWidget(self._central)
    
    def get_current_tab(self) -> Tuple[ColumnsAndLabels, DualPlot]:
        widget = self._tabs_widget.currentWidget()
        index = self._tabs_widget.currentIndex()
        return list(Tabs.values())[index], widget

    # Getters and Setters
    def set_measurements(self, measurement_model: MeasurementListModel):
        self._list_view_measurements.setModel(measurement_model)

    def get_measurement_list(self) -> MeasurementListModel:
        return self._list_view_measurements.model()

    def get_selected_measurements(self) -> Tuple[OpticsMeasurement]:
        selected = self._list_view_measurements.selectedIndexes()
        return tuple(s.data(role=Qt.EditRole) for s in selected)

    def set_selected_measurements(self, indices: Sequence[QModelIndex] = ()):
        self._list_view_measurements.selectionModel().clear()
        for idx in indices:
            self._list_view_measurements.selectionModel().select(idx, QItemSelectionModel.Select)

    def set_segments(self, segment_model: SegmentTableModel):
        self._table_segments.setModel(segment_model)
        self._table_segments.selectionModel().selectionChanged.connect(self._handle_table_segments_selected)

    def get_segments(self) -> SegmentTableModel:
        return self._table_segments.model()

    def get_selected_segments(self) -> Tuple[SegmentItemModel]:
        selected: List[QModelIndex] = self._table_segments.selectedIndexes()
        return tuple(s.data(role=Qt.EditRole) for s in selected if s.column() == 0)  # need only one per row
    
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


class MeasurementListView(QtWidgets.QListView):
    
    def __init__(self):
        super().__init__()
        self.setModel(MeasurementListModel())
        self.setItemDelegate(ColoredItemDelegate())
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setStyleSheet(MONOSPACED_TOOLTIP)


class SegmentTableView(QtWidgets.QTableView):

    def __init__(self):
        super().__init__()
        self.setModel(SegmentTableModel())
        header_hor = self.horizontalHeader()
        header_hor.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)       
        header_hor.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)

        header_ver = self.verticalHeader()
        header_ver.setVisible(False)
        header_ver.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)

        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setShowGrid(True)
        self.setStyleSheet(MONOSPACED_TOOLTIP)
    
    # def mousePressEvent(self, e: QtGui.QMouseEvent) -> None:
    #     idx = self.indexAt(e.pos())
    #     if e.button() == Qt.RightButton:
    #         self.model().toggle_row(idx)  # rather a controller thing?
    #         return 
    #     super().mousePressEvent(e)


class ColoredItemDelegate(QtWidgets.QStyledItemDelegate):

    COLOR_MAP = {
        MeasurementListModel.ColorIDs.NONE: colors.TEXT_DARK,
        MeasurementListModel.ColorIDs.BEAM1: colors.BEAM1,
        MeasurementListModel.ColorIDs.BEAM2: colors.BEAM2,
        MeasurementListModel.ColorIDs.RING1: colors.RING1,
        MeasurementListModel.ColorIDs.RING2: colors.RING2,
        MeasurementListModel.ColorIDs.RING3: colors.RING3,
        MeasurementListModel.ColorIDs.RING4: colors.RING4,
    }
    def paint(self, painter, option, index):
        # Customize the text color
        color_id = index.data(Qt.TextColorRole)
        try:
            color = self.COLOR_MAP[color_id]
        except KeyError:
            color = self.COLOR_MAP[MeasurementListModel.ColorIDs.NONE]
        option.palette.setColor(QtGui.QPalette.Text, QtGui.QColor(color))
        
        super().paint(painter, option, index)
