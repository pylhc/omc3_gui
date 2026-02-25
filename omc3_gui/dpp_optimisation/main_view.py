"""
Main View for DPP Optimisation
-------------------------------

This is the main view for the Closed Orbit (DPP) Optimisation application.
"""
from __future__ import annotations

import logging

from qtpy import QtWidgets
from qtpy.QtCore import Qt, Signal

from omc3_gui.dpp_optimisation.defaults import (
    DEFAULT_ANALYSIS_SUMMARY_TEXT,
    DEFAULT_ARC_INFO_TEXT,
    DEFAULT_DATAFILE_INFO_TEXT,
    DEFAULT_KNOB_FILES_SUMMARY_TEXT,
    DEFAULT_OPTIMISATION_INFO_TEXT,
)
from omc3_gui.ui_components import colors, styles
from omc3_gui.ui_components.base_classes_cvm import View
from omc3_gui.ui_components.widgets import (
    ChangeButton,
    DefaultButton,
    HorizontalSeparator,
    OpenButton,
    RemoveButton,
    RunButton,
)

LOGGER = logging.getLogger(__name__)


class DppOptimisationWindow(View):
    """Main window for DPP Optimisation."""

    WINDOW_TITLE = "Closed Orbit (DPP) Optimisation"
    _LOCKDOWN_CONTROL_NAMES = (
        "button_select_model",
        "button_update_model_energy",
        "button_copy_model_from_tab",
        "button_configure_arcs",
        "button_select_analysis_dir",
        "button_add_measurements",
        "button_add_measurement_folders",
        "button_remove_measurement",
        "button_add_optimisation_tab",
        "button_close_optimisation_tab",
        "button_configure_optimizer",
        "button_ssh_status",
        "button_set_env",
        "button_download_knobs",
        "button_create_datafile",
        "button_prepare_inputs_parallel",
        "button_run_optimisation",
        "button_save_results",
    )

    # Signals
    sig_select_model_dir = Signal()
    sig_copy_model_from_tab = Signal()
    sig_update_model_energy = Signal()
    sig_configure_arcs = Signal()
    sig_select_analysis_dir = Signal()
    sig_select_measurement_files = Signal()
    sig_select_measurement_folders = Signal()
    sig_remove_measurement_file = Signal()
    sig_add_optimisation_tab = Signal()
    sig_close_optimisation_tab = Signal()
    sig_close_optimisation_tab_at = Signal(int)
    sig_optimisation_tab_changed = Signal(int)
    sig_rename_optimisation_tab = Signal(int)
    sig_configure_optimizer = Signal()
    sig_download_knobs = Signal()
    sig_create_datafile = Signal()
    sig_prepare_inputs_parallel = Signal()
    sig_run_optimisation = Signal()
    sig_save_results = Signal()
    sig_view_results = Signal()
    sig_test_ssh_connection = Signal()
    sig_set_env = Signal()
    sig_soft_interrupt = Signal()
    sig_hard_interrupt = Signal()
    sig_arc_selection_changed = Signal(int)  # Arc index

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.WINDOW_TITLE)

        # UI Components (will be created in _build_ui)
        self._model_dir_label: QtWidgets.QLabel = None
        self._beam_label: QtWidgets.QLabel = None
        self._sequence_label: QtWidgets.QLabel = None
        self._beam_energy_label: QtWidgets.QLabel = None
        self._num_bpms_label: QtWidgets.QLabel = None

        self._arc_dropdown: QtWidgets.QComboBox = None
        self._measurement_list: QtWidgets.QListView = None
        self._analysis_summary_label: QtWidgets.QLabel = None
        self._optimisation_tabs: QtWidgets.QTabBar = None

        self._fixed_bpm_checkbox: QtWidgets.QCheckBox = None

        self.button_select_model: QtWidgets.QPushButton = None
        self.button_update_model_energy: QtWidgets.QPushButton = None
        self.button_copy_model_from_tab: QtWidgets.QPushButton = None
        self.button_configure_arcs: QtWidgets.QPushButton = None
        self.button_select_analysis_dir: QtWidgets.QPushButton = None
        self.button_add_measurements: QtWidgets.QPushButton = None
        self.button_add_measurement_folders: QtWidgets.QPushButton = None
        self.button_remove_measurement: QtWidgets.QPushButton = None
        self.button_add_optimisation_tab: QtWidgets.QPushButton = None
        self.button_close_optimisation_tab: QtWidgets.QPushButton = None
        self.button_configure_optimizer: QtWidgets.QPushButton = None
        self.button_ssh_status: QtWidgets.QPushButton = None
        self.button_set_env: QtWidgets.QPushButton = None
        self._ssh_env_label: QtWidgets.QLabel = None
        self.button_download_knobs: QtWidgets.QPushButton = None
        self.button_create_datafile: QtWidgets.QPushButton = None
        self.button_prepare_inputs_parallel: QtWidgets.QPushButton = None
        self.button_run_optimisation: QtWidgets.QPushButton = None
        self.button_save_results: QtWidgets.QPushButton = None
        self.button_view_results: QtWidgets.QPushButton = None
        self._knob_files_summary: QtWidgets.QLabel = None
        self._datafile_info_label: QtWidgets.QLabel = None
        self._optimisation_info_label: QtWidgets.QPlainTextEdit = None
        self._bottom_progress_label: QtWidgets.QLabel = None
        self._bottom_progress_bar: QtWidgets.QProgressBar = None
        self._interrupt_soft_button: QtWidgets.QPushButton = None
        self._interrupt_hard_button: QtWidgets.QPushButton = None

        self._build_ui()
        self._configure_window_geometry()
        self._configure_log_console()
        self._setup_bottom_progress()

    def _configure_window_geometry(self):
        """Set a larger default/minimum window size for this dense workflow UI."""
        screen = QtWidgets.QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            width = max(int(available.width() * 0.8), 1450)
            height = max(int(available.height() * 0.85), 980)
            self.resize(width, height)
        self.setMinimumSize(1360, 900)

    def _configure_log_console(self):
        """Apply DPP-specific log console behavior."""
        log_console = getattr(self, "log_console", None)
        if log_console is None:
            return
        try:
            log_console.console.expanded = True
        except Exception:
            LOGGER.debug("Unable to set log console expanded state", exc_info=True)

        for area in log_console.findChildren(QtWidgets.QAbstractScrollArea):
            area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # Keep console visible but bias more space to optimisation content above.
        log_console.setMinimumHeight(80)
        self.resizeDocks([log_console], [100], Qt.Vertical)

    def _build_ui(self):
        """Build the user interface."""
        # Central widget
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QtWidgets.QVBoxLayout(central_widget)

        # Global shared SSH/environment controls (outside tabbed optimisation context)
        global_ssh_row = QtWidgets.QHBoxLayout()
        self._ssh_env_label = QtWidgets.QLabel("Env: checking...")
        self._ssh_env_label.setToolTip("Remote Python environment status.")
        global_ssh_row.addWidget(self._ssh_env_label)
        self.button_set_env = DefaultButton("Set Env")
        self.button_set_env.clicked.connect(self.sig_set_env.emit)
        self.button_set_env.setToolTip("Set preferred remote Python executable.")
        global_ssh_row.addWidget(self.button_set_env)
        global_ssh_row.addStretch()
        self.button_ssh_status = DefaultButton("SSH: Checking...")
        self.button_ssh_status.clicked.connect(self.sig_test_ssh_connection.emit)
        self.button_ssh_status.setToolTip("Re-check optics SSH connectivity.")
        global_ssh_row.addWidget(self.button_ssh_status)
        main_layout.addLayout(global_ssh_row)

        tabs_row = QtWidgets.QHBoxLayout()
        tabs_row.addWidget(QtWidgets.QLabel("Optimisation Tabs:"))
        self._optimisation_tabs = QtWidgets.QTabBar()
        self._optimisation_tabs.setExpanding(False)
        self._optimisation_tabs.setMovable(False)
        self._optimisation_tabs.setContextMenuPolicy(Qt.CustomContextMenu)
        self._optimisation_tabs.currentChanged.connect(self.sig_optimisation_tab_changed.emit)
        self._optimisation_tabs.customContextMenuRequested.connect(self._on_tabs_context_menu)
        tabs_row.addWidget(self._optimisation_tabs, 1)
        self.button_add_optimisation_tab = DefaultButton("New")
        self.button_add_optimisation_tab.clicked.connect(self.sig_add_optimisation_tab.emit)
        tabs_row.addWidget(self.button_add_optimisation_tab)
        self.button_close_optimisation_tab = RemoveButton("Close")
        self.button_close_optimisation_tab.clicked.connect(self.sig_close_optimisation_tab.emit)
        tabs_row.addWidget(self.button_close_optimisation_tab)
        main_layout.addLayout(tabs_row)

        # Top row: model + arc configuration
        model_group = self._create_model_selection_group()
        arc_group = self._create_arc_configuration_group()
        settings_group = self._create_settings_group()
        top_row = QtWidgets.QHBoxLayout()
        top_row.addWidget(model_group, 2)
        top_row.addWidget(arc_group, 1)
        top_row.addWidget(settings_group, 1)
        main_layout.addLayout(top_row)

        # Middle row: measurements
        measurement_group = self._create_measurement_files_group()
        middle_row = QtWidgets.QHBoxLayout()
        middle_row.addWidget(measurement_group, 1)
        main_layout.addLayout(middle_row)

        # Bottom row: actions
        actions_group = self._create_actions_group()
        actions_group.setMinimumHeight(300)
        actions_group.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.MinimumExpanding,
        )
        main_layout.addWidget(actions_group)
        main_layout.setStretch(0, 0)
        main_layout.setStretch(1, 0)
        main_layout.setStretch(2, 3)
        main_layout.setStretch(3, 4)
        main_layout.setStretch(4, 3)

    def _on_tabs_context_menu(self, pos):
        """Open context menu for tab operations."""
        index = self._optimisation_tabs.tabAt(pos)
        if index < 0:
            return
        menu = QtWidgets.QMenu(self)
        add_action = menu.addAction("Add Tab")
        rename_action = menu.addAction("Rename Tab")
        delete_action = menu.addAction("Delete Tab")
        selected = menu.exec_(self._optimisation_tabs.mapToGlobal(pos))
        if selected == add_action:
            self.sig_add_optimisation_tab.emit()
        elif selected == rename_action:
            self.sig_rename_optimisation_tab.emit(index)
        elif selected == delete_action:
            self.sig_close_optimisation_tab_at.emit(index)

    def _create_model_selection_group(self) -> QtWidgets.QGroupBox:
        """Create the model selection group."""
        group = QtWidgets.QGroupBox("Model Selection")
        layout = QtWidgets.QVBoxLayout()

        # Button to select model directory
        button_layout = QtWidgets.QHBoxLayout()
        self.button_select_model = OpenButton("Select Model Directory")
        self.button_select_model.clicked.connect(self.sig_select_model_dir.emit)
        button_layout.addWidget(self.button_select_model)

        self.button_update_model_energy = ChangeButton("Update Model Energy")
        self.button_update_model_energy.clicked.connect(self.sig_update_model_energy.emit)
        self.button_update_model_energy.setEnabled(False)
        button_layout.addWidget(self.button_update_model_energy)

        self.button_copy_model_from_tab = DefaultButton("Copy Model From Tab")
        self.button_copy_model_from_tab.clicked.connect(self.sig_copy_model_from_tab.emit)
        self.button_copy_model_from_tab.setEnabled(False)
        button_layout.addWidget(self.button_copy_model_from_tab)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Info display
        info_layout = QtWidgets.QFormLayout()

        self._model_dir_label = QtWidgets.QLabel("Not selected")
        self._model_dir_label.setWordWrap(True)
        self._model_dir_label.setTextInteractionFlags(
            self._model_dir_label.textInteractionFlags()
            | Qt.TextSelectableByMouse
            | Qt.TextSelectableByKeyboard
        )
        info_layout.addRow("Model Directory:", self._model_dir_label)

        self._beam_label = QtWidgets.QLabel("-")
        self._beam_label.setTextInteractionFlags(
            self._beam_label.textInteractionFlags()
            | Qt.TextSelectableByMouse
            | Qt.TextSelectableByKeyboard
        )
        info_layout.addRow("Beam:", self._beam_label)

        self._beam_energy_label = QtWidgets.QLabel("-")
        self._beam_energy_label.setTextInteractionFlags(
            self._beam_energy_label.textInteractionFlags()
            | Qt.TextSelectableByMouse
            | Qt.TextSelectableByKeyboard
        )
        info_layout.addRow("Beam Energy (GeV):", self._beam_energy_label)

        self._sequence_label = QtWidgets.QLabel("-")
        self._sequence_label.setWordWrap(True)
        self._sequence_label.setTextInteractionFlags(
            self._sequence_label.textInteractionFlags()
            | Qt.TextSelectableByMouse
            | Qt.TextSelectableByKeyboard
        )
        info_layout.addRow("Sequence File:", self._sequence_label)

        self._num_bpms_label = QtWidgets.QLabel("-")
        self._num_bpms_label.setTextInteractionFlags(
            self._num_bpms_label.textInteractionFlags()
            | Qt.TextSelectableByMouse
            | Qt.TextSelectableByKeyboard
        )
        info_layout.addRow("Number of BPMs:", self._num_bpms_label)

        layout.addLayout(info_layout)
        group.setLayout(layout)
        return group

    def _create_arc_configuration_group(self) -> QtWidgets.QGroupBox:
        """Create the arc configuration group."""
        group = QtWidgets.QGroupBox("Arc Configuration")
        layout = QtWidgets.QVBoxLayout()

        # Arc dropdown and configure button
        arc_layout = QtWidgets.QHBoxLayout()
        arc_layout.addWidget(QtWidgets.QLabel("Selected Arc:"))

        self._arc_dropdown = QtWidgets.QComboBox()
        self._arc_dropdown.currentIndexChanged.connect(self.sig_arc_selection_changed.emit)
        arc_layout.addWidget(self._arc_dropdown, 1)

        self.button_configure_arcs = ChangeButton("Configure Arcs")
        self.button_configure_arcs.clicked.connect(self.sig_configure_arcs.emit)
        self.button_configure_arcs.setEnabled(False)
        arc_layout.addWidget(self.button_configure_arcs)

        layout.addLayout(arc_layout)

        # Info about current arc
        self._arc_info_label = QtWidgets.QLabel(DEFAULT_ARC_INFO_TEXT)
        self._arc_info_label.setWordWrap(True)
        self._arc_info_label.setStyleSheet(styles.info_panel_style(padding_px=10))
        layout.addWidget(self._arc_info_label)

        group.setLayout(layout)
        return group

    def _create_measurement_files_group(self) -> QtWidgets.QGroupBox:
        """Create the measurement files group."""
        group = QtWidgets.QGroupBox("Measurement Files")
        layout = QtWidgets.QVBoxLayout()

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()

        self.button_select_analysis_dir = OpenButton("Select Analysis Dir")
        self.button_select_analysis_dir.clicked.connect(self.sig_select_analysis_dir.emit)
        button_layout.addWidget(self.button_select_analysis_dir)

        self.button_add_measurements = OpenButton("Add Files")
        self.button_add_measurements.clicked.connect(self.sig_select_measurement_files.emit)
        self.button_add_measurements.setEnabled(False)
        button_layout.addWidget(self.button_add_measurements)

        self.button_add_measurement_folders = OpenButton("Add Folders")
        self.button_add_measurement_folders.clicked.connect(
            self.sig_select_measurement_folders.emit
        )
        self.button_add_measurement_folders.setEnabled(False)
        button_layout.addWidget(self.button_add_measurement_folders)

        self.button_remove_measurement = RemoveButton("Remove Selected")
        self.button_remove_measurement.clicked.connect(self.sig_remove_measurement_file.emit)
        self.button_remove_measurement.setEnabled(False)
        button_layout.addWidget(self.button_remove_measurement)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # List view
        content_layout = QtWidgets.QHBoxLayout()
        self._measurement_list = QtWidgets.QListView()
        self._measurement_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        content_layout.addWidget(self._measurement_list, 2)

        self._analysis_summary_label = QtWidgets.QLabel(
            DEFAULT_ANALYSIS_SUMMARY_TEXT
        )
        self._analysis_summary_label.setWordWrap(True)
        self._analysis_summary_label.setTextInteractionFlags(
            self._analysis_summary_label.textInteractionFlags() | Qt.TextSelectableByMouse
        )
        self._analysis_summary_label.setMinimumWidth(320)
        self._analysis_summary_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        content_layout.addWidget(self._analysis_summary_label, 1)
        layout.addLayout(content_layout)

        group.setLayout(layout)
        return group

    def _create_settings_group(self) -> QtWidgets.QGroupBox:
        """Create the settings group."""
        group = QtWidgets.QGroupBox("Settings")
        layout = QtWidgets.QVBoxLayout()

        # Optimizer settings button
        optimizer_layout = QtWidgets.QHBoxLayout()
        self.button_configure_optimizer = ChangeButton("Configure Optimizer (Advanced)")
        self.button_configure_optimizer.clicked.connect(self.sig_configure_optimizer.emit)
        optimizer_layout.addWidget(self.button_configure_optimizer)
        optimizer_layout.addStretch()
        layout.addLayout(optimizer_layout)

        # Developer options
        layout.addWidget(HorizontalSeparator())
        dev_label = QtWidgets.QLabel("Developer Options:")
        dev_label.setStyleSheet(f"font-weight: bold; color: {colors.TEXT_DARK};")
        layout.addWidget(dev_label)

        self._fixed_bpm_checkbox = QtWidgets.QCheckBox("Use Fixed BPM Reference")
        self._fixed_bpm_checkbox.setChecked(False)
        self._fixed_bpm_checkbox.setToolTip(
            "If checked, uses fixed reference BPM approach.\n"
            "If unchecked, creates all combinations of start/end BPMs (Cartesian product)."
        )
        layout.addWidget(self._fixed_bpm_checkbox)

        group.setLayout(layout)
        return group

    def _create_actions_group(self) -> QtWidgets.QGroupBox:
        """Create the actions group."""
        group = QtWidgets.QGroupBox("Actions")
        layout = QtWidgets.QVBoxLayout()

        # Step 1: Download knobs
        step1_layout = QtWidgets.QHBoxLayout()
        step1_label = QtWidgets.QLabel("Step 1:")
        step1_layout.addWidget(step1_label)

        self.button_download_knobs = DefaultButton("Download Knobs")
        self.button_download_knobs.clicked.connect(self.sig_download_knobs.emit)
        self.button_download_knobs.setEnabled(False)
        step1_layout.addWidget(self.button_download_knobs, 1)

        self.button_create_datafile = DefaultButton("Create Datafile")
        self.button_create_datafile.clicked.connect(self.sig_create_datafile.emit)
        self.button_create_datafile.setEnabled(False)
        step1_layout.addWidget(self.button_create_datafile, 1)

        self.button_prepare_inputs_parallel = RunButton("Prepare Inputs (Parallel)")
        self.button_prepare_inputs_parallel.clicked.connect(self.sig_prepare_inputs_parallel.emit)
        self.button_prepare_inputs_parallel.setEnabled(False)
        step1_layout.addWidget(self.button_prepare_inputs_parallel, 1)
        layout.addLayout(step1_layout)

        self._datafile_info_label = QtWidgets.QLabel(
            DEFAULT_DATAFILE_INFO_TEXT
        )
        self._datafile_info_label.setWordWrap(True)
        self._datafile_info_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._datafile_info_label.setMinimumHeight(85)
        self._datafile_info_label.setMaximumHeight(120)
        self._datafile_info_label.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred,
            QtWidgets.QSizePolicy.Fixed,
        )
        self._datafile_info_label.setStyleSheet(styles.info_panel_style())
        self._datafile_info_label.setTextInteractionFlags(
            self._datafile_info_label.textInteractionFlags() | Qt.TextSelectableByMouse
        )

        self._knob_files_summary = QtWidgets.QLabel(
            DEFAULT_KNOB_FILES_SUMMARY_TEXT
        )
        self._knob_files_summary.setWordWrap(True)
        self._knob_files_summary.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._knob_files_summary.setMinimumHeight(85)
        self._knob_files_summary.setMaximumHeight(120)
        self._knob_files_summary.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred,
            QtWidgets.QSizePolicy.Fixed,
        )
        self._knob_files_summary.setStyleSheet(styles.info_panel_style())
        self._knob_files_summary.setTextInteractionFlags(
            self._knob_files_summary.textInteractionFlags()
            | Qt.TextSelectableByMouse
        )

        step1_info_row = QtWidgets.QHBoxLayout()
        step1_info_row.setSpacing(12)
        step1_info_row.addWidget(self._knob_files_summary, 1)
        step1_info_row.addWidget(self._datafile_info_label, 1)
        layout.addLayout(step1_info_row)

        # Step 2 and 3: action buttons side-by-side with dedicated info boxes
        actions_row = QtWidgets.QHBoxLayout()

        optimisation_col = QtWidgets.QVBoxLayout()
        optimisation_col.addSpacing(8)
        optimisation_buttons = QtWidgets.QHBoxLayout()

        self.button_run_optimisation = RunButton("Run Optimisation")
        self.button_run_optimisation.clicked.connect(self.sig_run_optimisation.emit)
        self.button_run_optimisation.setEnabled(False)
        optimisation_buttons.addWidget(self.button_run_optimisation, 1)

        self.button_save_results = DefaultButton("Save Results")
        self.button_save_results.clicked.connect(self.sig_save_results.emit)
        self.button_save_results.setEnabled(False)
        optimisation_buttons.addWidget(self.button_save_results, 1)

        self.button_view_results = DefaultButton("View Results")
        self.button_view_results.clicked.connect(self.sig_view_results.emit)
        self.button_view_results.setEnabled(False)
        optimisation_buttons.addWidget(self.button_view_results, 1)
        optimisation_col.addLayout(optimisation_buttons)

        self._optimisation_info_label = QtWidgets.QPlainTextEdit()
        self._optimisation_info_label.setReadOnly(True)
        self._optimisation_info_label.setLineWrapMode(QtWidgets.QPlainTextEdit.WidgetWidth)
        self._optimisation_info_label.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._optimisation_info_label.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._optimisation_info_label.setMinimumHeight(130)
        self._optimisation_info_label.setMaximumHeight(160)
        self._optimisation_info_label.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred,
            QtWidgets.QSizePolicy.MinimumExpanding,
        )
        self._optimisation_info_label.setStyleSheet(styles.info_panel_style())
        self._optimisation_info_label.setPlainText(
            DEFAULT_OPTIMISATION_INFO_TEXT
        )
        optimisation_col.addWidget(self._optimisation_info_label)
        actions_row.addLayout(optimisation_col, 1)

        layout.addLayout(actions_row)
        layout.setStretch(0, 0)  # Step 1 buttons
        layout.setStretch(1, 0)  # Step 1 info boxes (capped height)
        layout.setStretch(2, 1)  # Optimisation section gets extra height

        group.setLayout(layout)
        return group

    def _iter_lockdown_controls(self):
        """Yield controls that are disabled during optimisation runs."""
        for name in self._LOCKDOWN_CONTROL_NAMES:
            widget = getattr(self, name, None)
            if widget is not None:
                yield widget

    # Public methods for controller to update view
    def set_model_info(
        self,
        model_dir: str,
        beam: int,
        sequence_file: str,
        beam_energy: float,
        num_bpms: int,
    ):
        """Update the model information display."""
        self._model_dir_label.setText(model_dir)
        self._beam_label.setText(str(beam))
        self._sequence_label.setText(sequence_file)
        self._beam_energy_label.setText(f"{beam_energy:.1f}")
        self._num_bpms_label.setText(str(num_bpms) if num_bpms > 0 else "-")

    def set_measurement_list_model(self, model):
        """Set the model for the measurement list view."""
        self._measurement_list.setModel(model)

    def add_optimisation_tab(self, label: str) -> int:
        """Add a new optimisation tab and return index."""
        return self._optimisation_tabs.addTab(label)

    def remove_optimisation_tab(self, index: int):
        """Remove optimisation tab."""
        self._optimisation_tabs.removeTab(index)

    def rename_optimisation_tab(self, index: int, label: str):
        """Rename optimisation tab."""
        self._optimisation_tabs.setTabText(index, label)

    def set_current_optimisation_tab(self, index: int, emit_signal: bool = True):
        """Set current optimisation tab."""
        old = self._optimisation_tabs.blockSignals(not emit_signal)
        self._optimisation_tabs.setCurrentIndex(index)
        self._optimisation_tabs.blockSignals(old)

    def get_current_optimisation_tab(self) -> int:
        """Get current optimisation tab index."""
        return self._optimisation_tabs.currentIndex()

    def get_optimisation_tab_count(self) -> int:
        """Get optimisation tab count."""
        return self._optimisation_tabs.count()

    def get_optimisation_tab_label(self, index: int) -> str:
        """Get optimisation tab label."""
        return self._optimisation_tabs.tabText(index)

    def set_arc_dropdown_model(self, model):
        """Set the model for the arc dropdown."""
        self._arc_dropdown.setModel(model)

    def update_arc_info(self, info_text: str):
        """Update the arc information label."""
        self._arc_info_label.setText(info_text)

    def enable_arc_configuration(self, enabled: bool):
        """Enable or disable arc configuration button."""
        self.button_configure_arcs.setEnabled(enabled)

    def enable_model_energy_update(self, enabled: bool):
        """Enable or disable model energy update button."""
        self.button_update_model_energy.setEnabled(enabled)

    def enable_copy_model_from_tab(self, enabled: bool):
        """Enable or disable copy-model-from-tab button."""
        self.button_copy_model_from_tab.setEnabled(enabled)

    def enable_measurement_removal(self, enabled: bool):
        """Enable or disable measurement removal button."""
        self.button_remove_measurement.setEnabled(enabled)

    def enable_measurement_addition(self, enabled: bool):
        """Enable or disable measurement add-file/folder buttons."""
        self.button_add_measurements.setEnabled(enabled)
        self.button_add_measurement_folders.setEnabled(enabled)

    def update_analysis_summary(self, summary_text: str):
        """Update analysis directory summary text."""
        self._analysis_summary_label.setText(summary_text)

    def get_analysis_summary_text(self) -> str:
        """Get analysis summary text."""
        return self._analysis_summary_label.text()

    def enable_download_knobs(self, enabled: bool):
        """Enable or disable download knobs button."""
        self.button_download_knobs.setEnabled(enabled)

    def enable_create_datafile(self, enabled: bool):
        """Enable or disable create datafile button."""
        self.button_create_datafile.setEnabled(enabled)

    def enable_run_optimisation(self, enabled: bool):
        """Enable or disable run optimisation button."""
        self.button_run_optimisation.setEnabled(enabled)

    def enable_save_results(self, enabled: bool):
        """Enable or disable save results button."""
        self.button_save_results.setEnabled(enabled)

    def enable_view_results(self, enabled: bool):
        """Enable or disable view results button."""
        self.button_view_results.setEnabled(enabled)

    def enable_prepare_inputs_parallel(self, enabled: bool):
        """Enable or disable parallel prepare button."""
        self.button_prepare_inputs_parallel.setEnabled(enabled)

    def set_optimisation_lockdown(self, enabled: bool, allow_view_results: bool = False):
        """Lock or unlock interactive controls during optimisation runs."""
        if enabled:
            for widget in self._iter_lockdown_controls():
                widget.setEnabled(False)
            self._optimisation_tabs.setEnabled(True)
            self._optimisation_tabs.setContextMenuPolicy(Qt.NoContextMenu)
            self._arc_dropdown.setEnabled(False)
            self._measurement_list.setEnabled(False)
            self._fixed_bpm_checkbox.setEnabled(False)
            self.button_view_results.setEnabled(allow_view_results)
            return

        for widget in self._iter_lockdown_controls():
            widget.setEnabled(True)
        self.button_view_results.setEnabled(True)
        self._optimisation_tabs.setEnabled(True)
        self._optimisation_tabs.setContextMenuPolicy(Qt.CustomContextMenu)
        self._arc_dropdown.setEnabled(True)
        self._measurement_list.setEnabled(True)
        self._fixed_bpm_checkbox.setEnabled(True)

    def update_datafile_info(self, info_text: str):
        """Update datafile action info text."""
        self._datafile_info_label.setText(info_text)

    def get_datafile_info_text(self) -> str:
        """Get datafile action info text."""
        return self._datafile_info_label.text()

    def clear_datafile_info(self):
        """Reset datafile action info text."""
        self._datafile_info_label.setText(DEFAULT_DATAFILE_INFO_TEXT)

    def update_optimisation_info(self, info_text: str):
        """Update optimisation action info text."""
        self._optimisation_info_label.setPlainText(info_text)

    def get_optimisation_info_text(self) -> str:
        """Get optimisation action info text."""
        return self._optimisation_info_label.toPlainText()

    def clear_optimisation_info(self):
        """Reset optimisation action info text."""
        self._optimisation_info_label.setPlainText(DEFAULT_OPTIMISATION_INFO_TEXT)

    def set_ssh_status(
        self,
        available: bool,
        text: str,
        tooltip: str = "",
        env_text: str = "",
        env_tooltip: str = "",
    ):
        """Set top-right SSH status button state and style."""
        self.button_ssh_status.setStyleSheet(styles.status_button_style(available))
        self.button_ssh_status.setText(text)
        self.button_ssh_status.setToolTip(tooltip or text)
        if env_text:
            self._ssh_env_label.setText(env_text)
        self._ssh_env_label.setToolTip(env_tooltip or env_text or self._ssh_env_label.toolTip())

    def update_knob_files_summary(
        self,
        magnet_count: int,
        corrector_count: int,
        magnet_file: str,
        corrector_file: str,
    ):
        """Update the knob file inspection summary."""
        self._knob_files_summary.setText(
            "Main magnet knobs: "
            f"{magnet_count}\n"
            "Corrector knobs: "
            f"{corrector_count}\n"
            "Magnet file: "
            f"{magnet_file}\n"
            "Corrector file: "
            f"{corrector_file}"
        )

    def set_knob_files_summary_text(self, text: str):
        """Set knob summary text directly."""
        self._knob_files_summary.setText(text)

    def get_knob_files_summary_text(self) -> str:
        """Get knob summary text."""
        return self._knob_files_summary.text()

    def set_arc_info_text(self, text: str):
        """Set arc info text directly."""
        self._arc_info_label.setText(text)

    def get_arc_info_text(self) -> str:
        """Get arc info text."""
        return self._arc_info_label.text()

    def clear_model_info(self):
        """Reset model info labels."""
        self._model_dir_label.setText("Not selected")
        self._beam_label.setText("-")
        self._sequence_label.setText("-")
        self._beam_energy_label.setText("-")
        self._num_bpms_label.setText("-")

    def clear_knob_files_summary(self):
        """Reset knob file inspection summary."""
        self._knob_files_summary.setText(DEFAULT_KNOB_FILES_SUMMARY_TEXT)

    def _setup_bottom_progress(self):
        """Create persistent bottom progress display."""
        status_bar = self.statusBar()
        self._bottom_progress_label = QtWidgets.QLabel("Idle")
        self._bottom_progress_bar = QtWidgets.QProgressBar()
        self._interrupt_soft_button = ChangeButton("Soft Interrupt")
        self._interrupt_hard_button = RemoveButton("Hard Interrupt")
        self._interrupt_soft_button.clicked.connect(self.sig_soft_interrupt.emit)
        self._interrupt_hard_button.clicked.connect(self.sig_hard_interrupt.emit)
        self._bottom_progress_bar.setMinimumWidth(260)
        self._bottom_progress_bar.setMaximumWidth(420)
        self._bottom_progress_bar.setRange(0, 100)
        self._bottom_progress_bar.setValue(0)
        self._bottom_progress_label.setVisible(False)
        self._bottom_progress_bar.setVisible(False)
        self._interrupt_soft_button.setVisible(False)
        self._interrupt_hard_button.setVisible(False)
        status_bar.addPermanentWidget(self._bottom_progress_label)
        status_bar.addPermanentWidget(self._bottom_progress_bar)
        status_bar.addPermanentWidget(self._interrupt_soft_button)
        status_bar.addPermanentWidget(self._interrupt_hard_button)

    def update_bottom_progress(
        self,
        text: str,
        value: int,
        maximum: int = 100,
        indeterminate: bool = False,
        visible: bool = True,
    ):
        """Update bottom progress display."""
        self._bottom_progress_label.setVisible(visible)
        self._bottom_progress_bar.setVisible(visible)
        self._bottom_progress_label.setText(text)
        if indeterminate:
            self._bottom_progress_bar.setRange(0, 0)
        else:
            self._bottom_progress_bar.setRange(0, maximum)
            self._bottom_progress_bar.setValue(value)

    def clear_bottom_progress(self):
        """Hide and reset bottom progress display."""
        self._bottom_progress_label.setText("Idle")
        self._bottom_progress_bar.setRange(0, 100)
        self._bottom_progress_bar.setValue(0)
        self._bottom_progress_label.setVisible(False)
        self._bottom_progress_bar.setVisible(False)

    def set_interrupt_controls_visible(self, visible: bool):
        """Show or hide soft/hard interrupt controls in status bar."""
        self._interrupt_soft_button.setVisible(visible)
        self._interrupt_hard_button.setVisible(visible)
        self._interrupt_soft_button.setEnabled(visible)
        self._interrupt_hard_button.setEnabled(visible)

    def get_selected_measurement_index(self) -> int:
        """Get the index of the selected measurement."""
        indexes = self._measurement_list.selectedIndexes()
        if indexes:
            return indexes[0].row()
        return -1

    def get_selected_arc_index(self) -> int:
        """Get the index of the selected arc."""
        return self._arc_dropdown.currentIndex()

    def is_fixed_bpm_enabled(self) -> bool:
        """Check if fixed BPM mode is enabled."""
        return self._fixed_bpm_checkbox.isChecked()

    def set_fixed_bpm_enabled(self, enabled: bool):
        """Set fixed BPM mode checkbox."""
        self._fixed_bpm_checkbox.setChecked(enabled)
