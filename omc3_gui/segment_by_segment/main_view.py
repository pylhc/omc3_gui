
# from omc3_gui.segment_by_segment.segment_by_segment_ui import Ui_main_window
import logging
from typing import Dict, List, Sequence, Tuple
from PyQt5 import QtGui

from qtpy import QtWidgets, QtGui
from qtpy.QtCore import Qt, Signal, Slot, QModelIndex, QItemSelection, QItemSelectionModel


from omc3_gui.plotting.classes import DualPlot
from omc3_gui.segment_by_segment.main_model import MeasurementListModel, SegmentTableModel
from omc3_gui.segment_by_segment.measurement_model import OpticsMeasurement
from omc3_gui.segment_by_segment.segment_model import SegmentModel
from omc3_gui.utils.base_classes import View
from omc3_gui.utils.counter import HorizontalGridLayoutFiller
from omc3_gui.utils.widgets import DefaultButton, EditButton, OpenButton, RemoveButton, RunButton
from omc3_gui.utils import colors

LOGGER = logging.getLogger(__name__)

class Tab:
    PHASE: str = "Phase"


class SbSWindow(View):
    WINDOW_TITLE = "OMC Segment-by-Segment"

    # QtSignals need to be defined as class-attributes
    # Optics Measurements ---
    sig_load_button_clicked = Signal()
    sig_remove_button_clicked = Signal()
    sig_matcher_button_clicked = Signal()
    sig_edit_optics_button_clicked = Signal(OpticsMeasurement)
    sig_list_optics_double_clicked = Signal(OpticsMeasurement)
    sig_list_optics_selected = Signal(tuple)  # Tuple[OpticsMeasurement]

    # Segments ---
    sig_run_segment_button_clicked = Signal()
    sig_remove_segment_button_clicked = Signal(tuple)
    sig_copy_segment_button_clicked = Signal(tuple)
    sig_new_segment_button_clicked = Signal()
    sig_default_segments_button_clicked = Signal()
    sig_load_segments_button_clicked = Signal()
    sig_table_segments_selected = Signal(tuple)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.WINDOW_TITLE)
        
        # List of UI elements accessible as instance-attributes:
        # Widgets ---
        self._cental: QtWidgets.QSplitter = None
        self._tabs_widget: QtWidgets.QTabWidget = None
        self._tabs: Dict[str, DualPlot] = None
        self._list_view_measurements: QtWidgets.QListView = None
        self._table_segments: QtWidgets.QTableView = None

        # Buttons ---
        self._button_load: QtWidgets.QPushButton = None
        self._button_remove: QtWidgets.QPushButton = None
        self._button_edit: QtWidgets.QPushButton = None
        self._button_matcher: QtWidgets.QPushButton = None

        self._button_run_segment: QtWidgets.QPushButton = None
        self._button_remove_segment: QtWidgets.QPushButton = None
        self._button_copy_segment: QtWidgets.QPushButton = None
        self._button_new_segment: QtWidgets.QPushButton = None
        self._button_default_segments: QtWidgets.QPushButton = None
        self._button_load_segments: QtWidgets.QPushButton = None
        
        self._build_gui()
        self._connect_signals()

        self.plot()

    def _connect_signals(self):
        # Optics Measurements ---
        self._button_load.clicked.connect(self._handle_load_files_button_clicked)
        self._button_edit.clicked.connect(self._handle_edit_measurement_button_clicked)
        self._list_view_measurements.doubleClicked.connect(self._handle_list_measurements_double_clicked)
        self._list_view_measurements.selectionModel().selectionChanged.connect(self._handle_list_measurements_selected)

        # Segments ---
        self._button_run_segment.clicked.connect(self._handle_run_segment_button_clicked)
        self._button_remove_segment.clicked.connect(self._handle_remove_segment_button_clicked)
        self._button_copy_segment.clicked.connect(self._handle_copy_segment_button_clicked)
        self._button_new_segment.clicked.connect(self._handle_new_segment_button_clicked)
        self._button_default_segments.clicked.connect(self._handle_default_segments_button_clicked)
        self._button_load_segments.clicked.connect(self._handle_load_segments_button_clicked)
        self._table_segments.selectionModel().selectionChanged.connect(self._handle_table_segments_selected)

    # Slots --------------------------------------------------------------------
    @Slot()
    def _handle_load_files_button_clicked(self):
        LOGGER.debug("Loading Optics files button clicked.")
        self.sig_load_button_clicked.emit()

    @Slot()
    def _handle_edit_measurement_button_clicked(self):
        LOGGER.debug("Edit Measurement button clicked.")
        selected = self._list_view_measurements.selectedIndexes()
        if len(selected) == 0:
            LOGGER.error("No measurement selected!")
            return
        
        if len(selected) > 1:
            LOGGER.error("More than one measurement selected!")
            return

        measurement = selected[0].data(role=Qt.EditRole)
        self.sig_edit_optics_button_clicked.emit(measurement)

    @Slot(QModelIndex)
    def _handle_list_measurements_double_clicked(self, idx):
        LOGGER.debug(f"Entry in Optics List double-clicked: {idx.data(role=Qt.DisplayRole)}")
        self.sig_list_optics_double_clicked.emit(idx.data(role=Qt.EditRole))

    @Slot()
    def _handle_list_measurements_selected(self):        
        LOGGER.debug("Optics List selection changed.")
        selected_measurements = self.get_selected_measurements()
        if len(selected_measurements) == 0:
            return
        self.sig_list_optics_selected.emit(selected_measurements)

    @Slot()
    def _handle_new_segment_button_clicked(self):
        LOGGER.debug("New Segment button clicked.")
        self.sig_new_segment_button_clicked.emit()

    @Slot()
    def _handle_run_segment_button_clicked(self):
        LOGGER.debug("Run Segment button clicked.")
        self.sig_run_segment_button_clicked.emit()

    @Slot()
    def _handle_remove_segment_button_clicked(self):
        LOGGER.debug("Remove Segment button clicked.")
        segments = self.get_selected_segments()
        if len(segments) == 0:
            LOGGER.debug("Nothing to remove.")
            return
        self.sig_remove_segment_button_clicked.emit(segments)

    @Slot()
    def _handle_copy_segment_button_clicked(self):
        LOGGER.debug("Copy Segment button clicked.")
        segments = self.get_selected_segments()
        if len(segments) == 0:
            LOGGER.debug("Nothing to copy.")
            return
        self.sig_copy_segment_button_clicked.emit(segments)

    @Slot()
    def _handle_default_segments_button_clicked(self):
        LOGGER.debug("Default Segments button clicked.")
        self.sig_default_segments_button_clicked.emit()

    @Slot()
    def _handle_load_segments_button_clicked(self):
        LOGGER.debug("Load Segments button clicked.")
        self.sig_load_segments_button_clicked.emit()

    @Slot()
    def _handle_table_segments_selected(self):
        LOGGER.debug("Segment Table selection changed.")
        selected_segments = self.get_selected_segments()
        if len(selected_segments) == 0:
            return
        self.sig_table_segment_selected.emit(selected_segments)

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
                    grid_buttons_filler = HorizontalGridLayoutFiller(layout=grid_buttons, cols=2)

                    load = OpenButton("Load")
                    grid_buttons_filler.add(load)
                    self._button_load = load

                    remove = RemoveButton()
                    grid_buttons_filler.add(remove)
                    self._button_remove = remove

                    edit = EditButton()
                    grid_buttons_filler.add(edit, col_span=2)
                    self._button_edit = edit

                    matcher = RunButton("Run Matcher")
                    grid_buttons_filler.add(matcher, col_span=2)
                    self._button_matcher = matcher
                
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
                    self._button_run_segment = run

                    new = DefaultButton("New")
                    grid_buttons_filler.add(new)
                    self._button_new_segment = new
                    
                    default = DefaultButton("Add Defaults")
                    grid_buttons_filler.add(default)
                    self._button_default_segments = default

                    load = OpenButton("Load")
                    grid_buttons_filler.add(load)
                    self._button_load_segments = load


                    copy = EditButton("Copy")
                    grid_buttons_filler.add(copy)
                    self._button_copy_segment = copy

                    grid_buttons_filler.add(QtWidgets.QWidget())
                    
                    remove = RemoveButton("Remove")
                    grid_buttons_filler.add(remove)
                    self._button_remove_segment = remove
                
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


    # Getters and Setters
    def set_measurements(self, measurement_model: MeasurementListModel):
        self._list_view_measurements.setModel(measurement_model)

    def get_measurement_list(self) -> MeasurementListModel:
        return self._list_view_measurements.model()

    def get_selected_measurements(self) -> Tuple[OpticsMeasurement]:
        selected = self._list_view_measurements.selectedIndexes()
        return tuple(s.data(role=Qt.EditRole) for s in selected)

    def set_selected_measurements(self, indices: Sequence[QModelIndex]):
        self._list_view_measurements.selectionModel().clear()
        for idx in indices:
            self._list_view_measurements.selectionModel().select(idx, QItemSelectionModel.Select)

    def set_segments(self, segment_model: SegmentTableModel):
        self._table_segments.setModel(segment_model)

    def get_segments(self) -> SegmentTableModel:
        return self._table_segments.model()

    def get_selected_segments(self) -> Tuple[SegmentModel]:
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
        tooltip_style = f"""
            QToolTip {{
                background-color: {colors.TOOLTIP_BACKGROUND}; /* Light gray background */
                color: {colors.TOOLTIP_TEXT}; /* Dark gray text */
                border: 1px solid {colors.TOOLTIP_BORDER}; /* Gray border */
                font-family: "Courier New", monospace; /* Monospaced font */
            }}
        """
        self.setStyleSheet(tooltip_style)


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
