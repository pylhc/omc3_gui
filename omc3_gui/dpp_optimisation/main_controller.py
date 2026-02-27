"""
Main Controller for DPP Optimisation
-------------------------------------

This is the main controller for the Closed Orbit (DPP) Optimisation application.
"""

from __future__ import annotations

import ast
import configparser
import copy
import ctypes
import dataclasses
import getpass
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import pyqtgraph as pg
from aba_optimiser.accelerators import LHC
from aba_optimiser.mad import GenericMadInterface
from aba_optimiser.model_creator import make_madx_sequence
from qtpy import QtWidgets
from qtpy.QtCore import Qt, QUrl, Slot
from qtpy.QtWidgets import QAbstractItemView, QApplication, QHeaderView, QTableWidget

from omc3_gui.dpp_optimisation.arc_config_dialog import ArcConfigDialog
from omc3_gui.dpp_optimisation.defaults import (
    DEFAULT_ANALYSIS_SUMMARY_TEXT,
    DEFAULT_ARC_INFO_TEXT,
    DEFAULT_DATAFILE_INFO_TEXT,
    DEFAULT_KNOB_FILES_SUMMARY_TEXT,
    DEFAULT_OPTIMISATION_INFO_TEXT,
    OptimiserConfig,
    SimulationConfig,
)
from omc3_gui.dpp_optimisation.main_model import (
    ArcListModel,
    BpmInfo,
    MeasurementFileListModel,
    ModelInfo,
)
from omc3_gui.dpp_optimisation.main_view import DppOptimisationWindow
from omc3_gui.dpp_optimisation.optimizer_dialog import OptimizerSettingsDialog
from omc3_gui.dpp_optimisation.services import (
    optimisation_service,
    preparation_service,
)
from omc3_gui.plotting.latex_to_html import latex_to_html_converter
from omc3_gui.ui_components import colors, styles
from omc3_gui.ui_components.base_classes_cvm import Controller as BaseController
from omc3_gui.ui_components.file_dialogs import (
    OpenDirectoriesDialog,
    OpenDirectoryDialog,
    OpenFilesDialog,
    SaveFileDialog,
)
from omc3_gui.ui_components.input_dialogs import (
    ask_double_dialog,
    ask_item_dialog,
    ask_text_dialog,
)
from omc3_gui.ui_components.message_boxes import (
    show_confirmation_dialog,
    show_error_dialog,
    show_info_dialog,
)

if TYPE_CHECKING:
    from aba_optimiser.measurements.knob_extraction import NXCALSResult

LOGGER = logging.getLogger(__name__)
BETABEAT_PATH = Path("/user/slops/data/LHC_DATA/OP_DATA/Betabeat/")

@dataclasses.dataclass
class OptimisationTabContext:
    """Complete per-tab optimisation context."""

    name: str
    model_info: ModelInfo | None = None
    arc_list_model: ArcListModel = dataclasses.field(default_factory=ArcListModel)
    measurement_list_model: MeasurementFileListModel = dataclasses.field(
        default_factory=MeasurementFileListModel
    )
    optimizer_config: OptimiserConfig = dataclasses.field(default_factory=OptimiserConfig)
    simulation_config: SimulationConfig = dataclasses.field(default_factory=SimulationConfig)
    knob_files_summary_text: str = DEFAULT_KNOB_FILES_SUMMARY_TEXT
    datafile_info_text: str = DEFAULT_DATAFILE_INFO_TEXT
    optimisation_info_text: str = DEFAULT_OPTIMISATION_INFO_TEXT
    analysis_summary_text: str = DEFAULT_ANALYSIS_SUMMARY_TEXT
    arc_info_text: str = DEFAULT_ARC_INFO_TEXT

    knobs_downloaded: bool = False
    datafile_created: bool = False
    measurement_datafile: Path | None = None
    analysis_dir: Path | None = None
    analysis_ini_file: Path | None = None
    previous_analysis_dir: Path | None = None
    bad_bpms: list[str] = dataclasses.field(default_factory=list)
    remote_host: str | None = None
    remote_work_dir: str | None = None
    remote_python_executable: str | None = None
    remote_magnet_knobs_file: str | None = None
    remote_corrector_knobs_file: str | None = None
    remote_measurement_datafile: str | None = None
    optimisation_results_file: Path | None = None
    latest_deltap_wrt_ref_results: list[float] = dataclasses.field(default_factory=list)
    latest_fitted_deltap_wrt_model_energy: list[float] = dataclasses.field(default_factory=list)
    latest_model_energy_gev: float | None = None
    latest_ref_energy: float | None = None
    prepare_inputs_running: bool = False
    fixed_bpm_enabled: bool = False
    temp_work_dir: tempfile.TemporaryDirectory | None = None
    analysis_context_revision: int = 0


class DppOptimisationController(BaseController):
    """Controller for the DPP Optimisation GUI."""

    MAGNET_KNOBS_FILENAME = "magnet_knobs.txt"
    CORRECTOR_KNOBS_FILENAME = "corrector_knobs.txt"
    MEASUREMENT_DATAFILE_FILENAME = "pz_data.parquet"
    SSH_CONNECT_TIMEOUT_SECONDS = 5
    SSH_COMMAND_TIMEOUT_SECONDS = 20
    SCP_COMMAND_TIMEOUT_SECONDS = 30
    SOFT_INTERRUPT_AUTO_ESCALATE_SECONDS = 3.0
    DEFAULT_ANALYSIS_SUMMARY = DEFAULT_ANALYSIS_SUMMARY_TEXT
    _SUPERSCRIPT_DIGITS = str.maketrans({
        "-": "⁻",
        "0": "⁰",
        "1": "¹",
        "2": "²",
        "3": "³",
        "4": "⁴",
        "5": "⁵",
        "6": "⁶",
        "7": "⁷",
        "8": "⁸",
        "9": "⁹",
    })
    _TAB_STATE_REF_FIELDS = (
        ("_arc_list_model", "arc_list_model"),
        ("_measurement_list_model", "measurement_list_model"),
        ("_optimizer_config", "optimizer_config"),
        ("_simulation_config", "simulation_config"),
        ("_measurement_datafile", "measurement_datafile"),
        ("_analysis_dir", "analysis_dir"),
        ("_analysis_ini_file", "analysis_ini_file"),
        ("_previous_analysis_dir", "previous_analysis_dir"),
        ("_remote_host", "remote_host"),
        ("_remote_work_dir", "remote_work_dir"),
        ("_remote_python_executable", "remote_python_executable"),
        ("_remote_magnet_knobs_file", "remote_magnet_knobs_file"),
        ("_remote_corrector_knobs_file", "remote_corrector_knobs_file"),
        ("_remote_measurement_datafile", "remote_measurement_datafile"),
        ("_optimisation_results_file", "optimisation_results_file"),
        ("_latest_model_energy_gev", "latest_model_energy_gev"),
        ("_latest_ref_energy", "latest_ref_energy"),
        ("_prepare_inputs_running", "prepare_inputs_running"),
        ("_temp_work_dir", "temp_work_dir"),
    )
    _TAB_STATE_VALUE_FIELDS = (
        ("_knobs_downloaded", "knobs_downloaded"),
        ("_datafile_created", "datafile_created"),
        ("_analysis_context_revision", "analysis_context_revision"),
    )
    _TAB_STATE_LIST_FIELDS = (
        ("_bad_bpms", "bad_bpms"),
        ("_latest_deltap_wrt_ref_results", "latest_deltap_wrt_ref_results"),
        (
            "_latest_fitted_deltap_wrt_model_energy",
            "latest_fitted_deltap_wrt_model_energy",
        ),
    )

    _view: DppOptimisationWindow

    def __init__(self):
        super().__init__(DppOptimisationWindow())

        # Models
        self._model_info: ModelInfo | None = None
        self._arc_list_model = ArcListModel()
        self._measurement_list_model = MeasurementFileListModel()

        # MAD interface (will be initialized when model is loaded)
        self._accelerator: LHC | None = None
        self._mad_interface: GenericMadInterface | None = None

        # Configuration
        self._optimizer_config = OptimiserConfig()
        self._simulation_config = SimulationConfig()

        # State tracking
        self._knobs_downloaded = False
        self._datafile_created = False
        self._results_dir: Path | None = None
        self._measurement_datafile: Path | None = None
        self._analysis_dir: Path | None = None
        self._analysis_ini_file: Path | None = None
        self._previous_analysis_dir: Path | None = None
        self._bad_bpms: list[str] = []
        self._remote_host: str | None = None
        self._remote_work_dir: str | None = None
        self._remote_python_executable: str | None = None
        self._remote_magnet_knobs_file: str | None = None
        self._remote_corrector_knobs_file: str | None = None
        self._remote_measurement_datafile: str | None = None
        self._temp_work_dir: tempfile.TemporaryDirectory | None = None
        self._optimisation_results_file: Path | None = None
        self._latest_deltap_wrt_ref_results: list[float] = []
        self._latest_fitted_deltap_wrt_model_energy: list[float] = []
        self._latest_model_energy_gev: float | None = None
        self._latest_ref_energy: float | None = None
        self._prepare_inputs_running = False
        self._optimisation_running = False
        self._results_plot_dialog: QtWidgets.QDialog | None = None
        self._optimisation_tabs: list[OptimisationTabContext] = []
        self._active_tab_index = -1
        self._active_selection_model = None
        self._remote_python_override: str | None = None
        self._running_processes_count = 0
        self._running_processes_lock = threading.Lock()
        self._parallel_inputs_total = 0
        self._parallel_inputs_completed = 0
        self._parallel_inputs_lock = threading.Lock()
        self._interrupt_soft_event = threading.Event()
        self._interrupt_hard_event = threading.Event()
        self._soft_interrupt_requested_at: float | None = None
        self._interrupt_threads_lock = threading.Lock()
        self._interruptible_threads: set[int] = set()
        self._analysis_context_revision = 0

        # Set up the view
        self._initialise_optimisation_tabs()
        self._refresh_ssh_status_indicator(show_popup=False)

        # Connect signals
        self._connect_signals()
        self._view.destroyed.connect(self._on_view_destroyed)
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._cleanup_temp_work_dir)

    def _connect_signals(self):
        """Connect signals from the view to controller slots."""
        view = self._view

        view.sig_select_model_dir.connect(self._on_select_model_dir)
        view.sig_copy_model_from_tab.connect(self._on_copy_model_from_tab)
        view.sig_update_model_energy.connect(self._on_update_model_energy)
        view.sig_configure_arcs.connect(self._on_configure_arcs)
        view.sig_select_analysis_dir.connect(self._on_select_analysis_dir)
        view.sig_select_measurement_files.connect(self._on_select_measurement_files)
        view.sig_select_measurement_folders.connect(self._on_select_measurement_folders)
        view.sig_remove_measurement_file.connect(self._on_remove_measurement_file)
        view.sig_add_optimisation_tab.connect(self._on_add_optimisation_tab)
        view.sig_close_optimisation_tab.connect(self._on_close_optimisation_tab)
        view.sig_close_optimisation_tab_at.connect(self._on_close_optimisation_tab_at)
        view.sig_optimisation_tab_changed.connect(self._on_optimisation_tab_changed)
        view.sig_rename_optimisation_tab.connect(self._on_rename_optimisation_tab)
        view.sig_configure_optimizer.connect(self._on_configure_optimizer)
        view.sig_download_knobs.connect(self._on_download_knobs)
        view.sig_create_datafile.connect(self._on_create_datafile)
        view.sig_prepare_inputs_parallel.connect(self._on_prepare_inputs_parallel)
        view.sig_run_optimisation.connect(self._on_run_optimisation)
        view.sig_soft_interrupt.connect(self._on_soft_interrupt)
        view.sig_hard_interrupt.connect(self._on_hard_interrupt)
        view.sig_save_results.connect(self._on_save_results)
        view.sig_view_results.connect(self._on_view_results)
        view.sig_test_ssh_connection.connect(self._on_test_ssh_connection)
        view.sig_set_env.connect(self._on_set_env)
        view.sig_arc_selection_changed.connect(self._on_arc_selection_changed)
        self._connect_measurement_selection_signal()

    def _connect_measurement_selection_signal(self):
        """Connect selectionChanged for the currently-bound measurement list model."""
        selection_model = self._view._measurement_list.selectionModel()
        if self._active_selection_model is not None:
            try:
                self._active_selection_model.selectionChanged.disconnect(
                    self._update_measurement_buttons
                )
            except Exception:
                pass
        if selection_model is not None:
            selection_model.selectionChanged.connect(self._update_measurement_buttons)
            self._active_selection_model = selection_model

    def _initialise_optimisation_tabs(self):
        """Create initial optimisation tab context."""
        self._optimisation_tabs = [OptimisationTabContext(name="Optimisation 1")]
        self._view.add_optimisation_tab("Optimisation 1")
        self._view.set_current_optimisation_tab(0, emit_signal=False)
        self._apply_tab_context(0)

    @staticmethod
    def _clone_arc_list_model(model: ArcListModel) -> ArcListModel:
        """Create an independent copy of an arc list model."""
        clone = ArcListModel()
        for arc in model.get_all_arcs():
            clone.add_arc(copy.deepcopy(arc))
        return clone

    def _capture_current_tab_context(self):
        """Store current controller/view state into active tab context."""
        if self._active_tab_index < 0 or self._active_tab_index >= len(self._optimisation_tabs):
            return
        ctx = self._optimisation_tabs[self._active_tab_index]
        self._copy_controller_state_to_tab_context(ctx)
        ctx.analysis_summary_text = self._view.get_analysis_summary_text()
        ctx.arc_info_text = self._view.get_arc_info_text()
        ctx.knob_files_summary_text = self._view.get_knob_files_summary_text()
        ctx.datafile_info_text = self._view.get_datafile_info_text()
        ctx.optimisation_info_text = self._view.get_optimisation_info_text()
        ctx.fixed_bpm_enabled = self._view.is_fixed_bpm_enabled()

    def _copy_controller_state_to_tab_context(self, ctx: OptimisationTabContext):
        """Copy runtime controller state into the provided tab context."""
        ctx.model_info = copy.deepcopy(self._model_info) if self._model_info is not None else None
        for controller_attr, context_attr in self._TAB_STATE_REF_FIELDS:
            setattr(ctx, context_attr, getattr(self, controller_attr))
        for controller_attr, context_attr in self._TAB_STATE_VALUE_FIELDS:
            setattr(ctx, context_attr, getattr(self, controller_attr))
        for controller_attr, context_attr in self._TAB_STATE_LIST_FIELDS:
            setattr(ctx, context_attr, list(getattr(self, controller_attr)))

    def _apply_tab_context(self, index: int):
        """Load tab context into controller/view."""
        ctx = self._optimisation_tabs[index]
        self._restore_controller_state_from_tab_context(ctx)

        self._view.set_measurement_list_model(self._measurement_list_model)
        self._view.set_arc_dropdown_model(self._arc_list_model)
        self._connect_measurement_selection_signal()

        if self._model_info and self._model_info.sequence_file and self._model_info.beam is not None and self._model_info.beam_energy is not None:
            self._view.set_model_info(
                model_dir=str(self._model_info.model_dir),
                beam=self._model_info.beam,
                sequence_file=self._model_info.sequence_file.name,
                beam_energy=self._model_info.beam_energy,
                num_bpms=len(self._model_info.bpms),
            )
        else:
            self._view.clear_model_info()
        self._view.update_analysis_summary(ctx.analysis_summary_text)
        self._view.set_knob_files_summary_text(ctx.knob_files_summary_text)
        self._view.update_datafile_info(ctx.datafile_info_text)
        self._view.update_optimisation_info(ctx.optimisation_info_text)
        self._view.set_fixed_bpm_enabled(ctx.fixed_bpm_enabled)
        self._view.enable_arc_configuration(self._model_info is not None and self._model_info.beam is not None)
        self._view.enable_model_energy_update(self._model_info is not None and self._model_info.beam is not None)
        self._active_tab_index = index
        self._update_arc_info()
        self._update_measurement_buttons()
        self._update_action_buttons()

    def _restore_controller_state_from_tab_context(self, ctx: OptimisationTabContext):
        """Restore runtime controller state from the provided tab context."""
        self._model_info = copy.deepcopy(ctx.model_info) if ctx.model_info is not None else None
        for controller_attr, context_attr in self._TAB_STATE_REF_FIELDS:
            setattr(self, controller_attr, getattr(ctx, context_attr))
        for controller_attr, context_attr in self._TAB_STATE_VALUE_FIELDS:
            setattr(self, controller_attr, getattr(ctx, context_attr))
        for controller_attr, context_attr in self._TAB_STATE_LIST_FIELDS:
            setattr(self, controller_attr, list(getattr(ctx, context_attr)))

    def _add_betabeat_shortcut(self, dialog):
        """Add common sidebar shortcuts in file dialogs."""
        sidebar_urls = dialog.sidebarUrls()
        betabeat_url = QUrl.fromLocalFile(str(BETABEAT_PATH))
        cwd_url = QUrl.fromLocalFile(str(Path.cwd()))

        if betabeat_url not in sidebar_urls:
            sidebar_urls.append(betabeat_url)
        if cwd_url not in sidebar_urls:
            sidebar_urls.append(cwd_url)

        dialog.setSidebarUrls(sidebar_urls)

    def _get_measurement_dialog_start_dir(self) -> Path | None:
        """Get preferred start directory for measurement dialogs."""
        if self._model_info is None:
            return None

        model_dir = self._model_info.model_dir
        parts = model_dir.parts
        for idx, part in enumerate(parts):
            if part.lower() == "models" and idx > 0 and parts[idx - 1].upper().startswith("LHC"):
                if len(model_dir.parents) >= 2:
                    return model_dir.parents[1]
                return model_dir.parent

        return self._model_info.model_dir.parent

    def _cleanup_temp_work_dir(self):
        """Clean up all tab-scoped temporary working directories."""
        dirs: list[tempfile.TemporaryDirectory] = []
        seen: set[int] = set()
        for ctx in self._optimisation_tabs:
            if ctx.temp_work_dir is not None and id(ctx.temp_work_dir) not in seen:
                dirs.append(ctx.temp_work_dir)
                seen.add(id(ctx.temp_work_dir))
            ctx.temp_work_dir = None
        if self._temp_work_dir is not None and id(self._temp_work_dir) not in seen:
            dirs.append(self._temp_work_dir)
        self._temp_work_dir = None

        for td in dirs:
            try:
                td.cleanup()
            except Exception:
                LOGGER.warning("Failed to cleanup temporary directory", exc_info=True)

    def _get_temp_work_dir(self) -> Path:
        """Get active-tab temporary working directory for generated artifacts."""
        if self._temp_work_dir is None:
            tab_num = max(self._active_tab_index + 1, 1)
            self._temp_work_dir = tempfile.TemporaryDirectory(prefix=f"omc3_gui_work_tab{tab_num}_")
            if 0 <= self._active_tab_index < len(self._optimisation_tabs):
                self._optimisation_tabs[self._active_tab_index].temp_work_dir = self._temp_work_dir
        return Path(self._temp_work_dir.name)

    def _get_magnet_knobs_file(self) -> Path:
        """Path to the main magnet knobs file in the temporary work directory."""
        return self._get_temp_work_dir() / self.MAGNET_KNOBS_FILENAME

    def _get_corrector_knobs_file(self) -> Path:
        """Path to the corrector knobs file in the temporary work directory."""
        return self._get_temp_work_dir() / self.CORRECTOR_KNOBS_FILENAME

    def _clear_remote_artifacts(self):
        """Clear remote artifact tracking."""
        self._remote_host = None
        self._remote_work_dir = None
        self._remote_python_executable = None
        self._remote_magnet_knobs_file = None
        self._remote_corrector_knobs_file = None
        self._remote_measurement_datafile = None

    def _reset_optimisation_results_state(self):
        """Reset stored optimisation results and metadata."""
        self._optimisation_results_file = None
        self._latest_deltap_wrt_ref_results = []
        self._latest_fitted_deltap_wrt_model_energy = []
        self._latest_model_energy_gev = None
        self._latest_ref_energy = None

    def _reset_run_artifacts(self):
        """Reset generated artefacts that depend on current inputs/context."""
        self._knobs_downloaded = False
        self._datafile_created = False
        self._measurement_datafile = None
        self._clear_remote_artifacts()
        self._reset_optimisation_results_state()

    def _clear_action_info_panels(self):
        """Reset all action info panels in the UI."""
        self._view.clear_datafile_info()
        self._view.clear_optimisation_info()
        self._view.clear_knob_files_summary()

    @staticmethod
    def _reset_tab_action_info(ctx: OptimisationTabContext):
        """Reset tab action/info text blocks to default values."""
        ctx.arc_info_text = DEFAULT_ARC_INFO_TEXT
        ctx.knob_files_summary_text = DEFAULT_KNOB_FILES_SUMMARY_TEXT
        ctx.datafile_info_text = DEFAULT_DATAFILE_INFO_TEXT
        ctx.optimisation_info_text = DEFAULT_OPTIMISATION_INFO_TEXT

    @staticmethod
    def _clear_tab_remote_artifacts(ctx: OptimisationTabContext):
        """Clear remote artifact tracking for one tab context."""
        ctx.remote_host = None
        ctx.remote_work_dir = None
        ctx.remote_python_executable = None
        ctx.remote_magnet_knobs_file = None
        ctx.remote_corrector_knobs_file = None
        ctx.remote_measurement_datafile = None

    @classmethod
    def _reset_tab_run_artifacts(cls, ctx: OptimisationTabContext):
        """Reset tab artefacts generated from current measurement/model context."""
        ctx.knobs_downloaded = False
        ctx.datafile_created = False
        ctx.measurement_datafile = None
        cls._clear_tab_remote_artifacts(ctx)
        ctx.optimisation_results_file = None
        ctx.latest_deltap_wrt_ref_results = []
        ctx.latest_fitted_deltap_wrt_model_energy = []
        ctx.latest_model_energy_gev = None
        cls._reset_tab_action_info(ctx)

    @staticmethod
    def _configure_results_info_table(info_table: QTableWidget):
        """Apply common configuration for results summary table."""
        info_table.setColumnCount(4)
        info_table.setHorizontalHeaderLabels(["Tab", "Mean", "StdErr", "Results file"])
        info_table.verticalHeader().setVisible(False)
        info_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        info_table.setSelectionMode(QAbstractItemView.NoSelection)
        info_table.setAlternatingRowColors(True)
        info_table.setWordWrap(False)
        info_table.setMinimumHeight(190)
        info_table.horizontalHeader().setStretchLastSection(True)
        info_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        info_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        info_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        info_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        info_table.setStyleSheet(styles.readonly_table_style())

    @staticmethod
    def _configure_results_plot(plot: pg.PlotWidget, ref_energy: float):
        """Apply common visual configuration for results plot widget."""
        plot.setBackground(colors.WHITE)
        plot.showGrid(x=True, y=True, alpha=0.25)
        plot.getAxis("left").enableAutoSIPrefix(False)
        plot.setLabel("bottom", "Arc", color=colors.TEXT_DARK)
        plot.setLabel(
            "left",
            latex_to_html_converter(r"$\Delta p$ (w.r.t. " + str(int(ref_energy)) + " GeV)"),
            color=colors.TEXT_DARK,
        )
        plot.getAxis("left").setPen(pg.mkPen(colors.TEXT_DARK))
        plot.getAxis("left").setTextPen(pg.mkPen(colors.TEXT_DARK))
        plot.getAxis("bottom").setPen(pg.mkPen(colors.TEXT_DARK))
        plot.getAxis("bottom").setTextPen(pg.mkPen(colors.TEXT_DARK))
        plot.addLegend(labelTextColor=colors.TEXT_DARK)

    def _register_running_processes(self, count: int = 1):
        """Increase global running-process counter used in progress labels."""
        with self._running_processes_lock:
            was_idle = self._running_processes_count == 0
            self._running_processes_count = max(0, self._running_processes_count + max(0, count))
            is_running = self._running_processes_count > 0
        if was_idle and is_running:
            self._interrupt_soft_event.clear()
            self._interrupt_hard_event.clear()
            self._soft_interrupt_requested_at = None
        self._view.set_interrupt_controls_visible(is_running)

    def _unregister_running_processes(self, count: int = 1):
        """Decrease global running-process counter used in progress labels."""
        with self._running_processes_lock:
            self._running_processes_count = max(0, self._running_processes_count - max(0, count))
            is_running = self._running_processes_count > 0
        self._view.set_interrupt_controls_visible(is_running)
        if not is_running:
            self._interrupt_soft_event.clear()
            self._interrupt_hard_event.clear()
            self._soft_interrupt_requested_at = None
            with self._interrupt_threads_lock:
                self._interruptible_threads.clear()

    def _format_running_processes_text(self, text: str) -> str:
        """Append current global running-process count to a progress label."""
        with self._running_processes_lock:
            running = self._running_processes_count
        suffix = "process" if running == 1 else "processes"
        return f"{text} ({running} {suffix} running)"

    def _get_running_processes_count(self) -> int:
        """Return current global running-process count."""
        with self._running_processes_lock:
            return self._running_processes_count

    def _register_interrupt_thread(self, thread: threading.Thread | None):
        """Track a worker thread that can be interrupted via hard cancel."""
        if thread is None or not thread.ident:
            return
        with self._interrupt_threads_lock:
            self._interruptible_threads.add(thread.ident)

    def _unregister_interrupt_thread(self, thread: threading.Thread | None):
        """Stop tracking a worker thread once it has finished."""
        if thread is None or not thread.ident:
            return
        with self._interrupt_threads_lock:
            self._interruptible_threads.discard(thread.ident)

    def _interrupt_requested(self) -> bool:
        """Whether user requested any interruption."""
        return self._interrupt_soft_event.is_set() or self._interrupt_hard_event.is_set()

    def _maybe_auto_escalate_interrupt(self):
        """Auto-escalate soft interrupt to hard interrupt after timeout."""
        if self._interrupt_hard_event.is_set() or not self._interrupt_soft_event.is_set():
            return
        if self._soft_interrupt_requested_at is None:
            self._soft_interrupt_requested_at = time.monotonic()
            return
        elapsed = time.monotonic() - self._soft_interrupt_requested_at
        if elapsed >= self.SOFT_INTERRUPT_AUTO_ESCALATE_SECONDS:
            self._on_hard_interrupt()

    def _raise_if_interrupted(self):
        """Raise when user requested interruption."""
        if self._interrupt_requested():
            raise InterruptedError("Interrupted by user.")

    @staticmethod
    def _raise_async_in_thread(thread_id: int, exc_type: type[BaseException]) -> bool:
        """Inject an exception into a running Python thread."""
        if not thread_id:
            return False
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(thread_id),
            ctypes.py_object(exc_type),
        )
        if res == 0:
            return False
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(thread_id), None)
            return False
        return True

    @Slot()
    def _on_soft_interrupt(self):
        """Request SIGINT-like cancellation (Ctrl+C semantics)."""
        if self._get_running_processes_count() <= 0:
            return
        LOGGER.warning("Soft interrupt requested by user.")
        if self._soft_interrupt_requested_at is None:
            self._soft_interrupt_requested_at = time.monotonic()
        self._interrupt_soft_event.set()
        with self._interrupt_threads_lock:
            thread_ids = list(self._interruptible_threads)
        for thread_id in thread_ids:
            self._raise_async_in_thread(thread_id, KeyboardInterrupt)
        self._view.update_bottom_progress(
            text=self._format_running_processes_text("Soft interrupt (Ctrl+C) requested..."),
            value=0,
            maximum=1,
            indeterminate=True,
            visible=True,
        )

    @Slot()
    def _on_hard_interrupt(self):
        """Force SIGQUIT-like cancellation (Ctrl+\\ semantics)."""
        if self._get_running_processes_count() <= 0:
            return
        LOGGER.warning("Hard interrupt requested by user.")
        self._interrupt_soft_event.set()
        self._interrupt_hard_event.set()
        self._soft_interrupt_requested_at = None
        with self._interrupt_threads_lock:
            thread_ids = list(self._interruptible_threads)
        for thread_id in thread_ids:
            self._raise_async_in_thread(thread_id, SystemExit)
        self._view.update_bottom_progress(
            text=self._format_running_processes_text("Hard interrupt (Ctrl+\\) requested: terminating workers..."),
            value=0,
            maximum=1,
            indeterminate=True,
            visible=True,
        )

    def _register_parallel_inputs(self, count: int):
        """Register additional parallel-input tasks in the global progress pool."""
        with self._parallel_inputs_lock:
            if self._parallel_inputs_total > 0 and self._parallel_inputs_completed >= self._parallel_inputs_total:
                self._parallel_inputs_total = 0
                self._parallel_inputs_completed = 0
            self._parallel_inputs_total = max(0, self._parallel_inputs_total + max(0, count))

    def _mark_parallel_inputs_completed(self, count: int = 1):
        """Mark parallel-input tasks as completed in the global progress pool."""
        with self._parallel_inputs_lock:
            self._parallel_inputs_completed = min(
                self._parallel_inputs_total,
                max(0, self._parallel_inputs_completed + max(0, count)),
            )

    def _get_parallel_inputs_progress(self) -> tuple[int, int]:
        """Return (completed, total) for global parallel-input progress."""
        with self._parallel_inputs_lock:
            return self._parallel_inputs_completed, self._parallel_inputs_total

    def _get_remote_work_dir(self, beam: int) -> str:
        """Return remote working directory for generated artifacts."""
        username = getpass.getuser()
        tab_label = "tab1"
        if 0 <= self._active_tab_index < len(self._optimisation_tabs):
            ctx = self._optimisation_tabs[self._active_tab_index]
            if ctx.temp_work_dir is not None:
                tab_label = Path(ctx.temp_work_dir.name).name
            else:
                tab_label = f"tab{self._active_tab_index + 1}"
        return f"/tmp/omc3_gui_dpp_{username}_beam{beam}/{tab_label}"

    def _get_magnet_knobs_display_path(self) -> str:
        """Return path shown in UI for magnet knob file."""
        if self._remote_magnet_knobs_file:
            return self._format_remote_path_for_display(self._remote_magnet_knobs_file)
        return str(self._get_magnet_knobs_file().resolve())

    def _get_corrector_knobs_display_path(self) -> str:
        """Return path shown in UI for corrector knob file."""
        if self._remote_corrector_knobs_file:
            return self._format_remote_path_for_display(self._remote_corrector_knobs_file)
        return str(self._get_corrector_knobs_file().resolve())

    def _format_remote_path_for_display(self, path: str) -> str:
        """Render remote path with host marker for UI text."""
        host = self._remote_host or "remote"
        return f"{path} [remote:{host}]"

    def _get_ssh_host_for_beam(self, beam: int) -> str:
        """Return the optics server host for the beam."""
        return f"cs-ccr-optics{beam}.cern.ch"

    def _test_ssh_connection_to_host(self, host: str) -> tuple[bool, str]:
        """Check whether an SSH connection to host is available in batch mode."""
        result = self._run_ssh_command(host, "echo omc3_gui_ssh_ok")
        if result.returncode == 0 and "omc3_gui_ssh_ok" in result.stdout:
            return True, "Connection OK"

        stderr = result.stderr.strip() or result.stdout.strip() or "Unknown SSH error"
        return False, stderr

    def _probe_remote_server_for_beam(self, beam: int) -> tuple[bool, str, str, str]:
        """Return availability, host, message and remote python path for beam optics server."""
        host = self._get_ssh_host_for_beam(beam)
        available, message = self._test_ssh_connection_to_host(host)
        if not available:
            return available, host, message, ""

        runtime_ok, runtime_msg, remote_python = self._check_remote_python_runtime(host)
        if not runtime_ok:
            return False, host, runtime_msg, ""
        return True, host, "Connection and runtime OK", remote_python

    def _is_remote_server_available_for_beam(self, beam: int) -> tuple[bool, str, str]:
        """Return availability, host and message for beam-specific optics server."""
        available, host, message, _ = self._probe_remote_server_for_beam(beam)
        return available, host, message

    def _check_remote_python_runtime(self, host: str) -> tuple[bool, str, str]:
        """Ensure required Python modules are available on remote host for GUI interpreter."""
        gui_python = self._remote_python_override or sys.executable
        check_script = (
            "import sys\n"
            "import aba_optimiser\n"
            "import pandas\n"
            "print('omc3_gui_runtime_ok')\n"
            "print(sys.executable)\n"
        )
        cmd = (
            f"test -x {shlex.quote(gui_python)} && "
            f"{shlex.quote(gui_python)} -c {shlex.quote(check_script)}"
        )
        result = self._run_ssh_command(host, cmd)
        stdout_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if result.returncode == 0 and stdout_lines and "omc3_gui_runtime_ok" in stdout_lines:
            remote_py = stdout_lines[-1]
            return True, "Remote Python runtime OK", remote_py

        details = result.stderr.strip() or result.stdout.strip() or "Unknown runtime error"
        return (
            False,
            (
                "Remote does not provide the same GUI Python environment. "
                f"Expected executable: {gui_python}\n{details}"
            ),
            "",
        )

    def _get_remote_python_executable(self, host: str) -> str:
        """Get validated remote Python executable for host."""
        if self._remote_host == host and self._remote_python_executable:
            return self._remote_python_executable

        runtime_ok, runtime_msg, remote_python = self._check_remote_python_runtime(host)
        if not runtime_ok:
            raise RuntimeError(runtime_msg)
        return remote_python

    def _refresh_ssh_status_indicator(self, show_popup: bool = False):
        """Refresh top-right SSH status indicator and optionally show popup details."""
        if self._model_info and self._model_info.beam in (1, 2):
            beam = self._model_info.beam
            host = self._get_ssh_host_for_beam(beam)
            gui_py = self._remote_python_override or sys.executable
            available, _, message, remote_py = self._probe_remote_server_for_beam(beam)
            status_text = f"SSH B{beam}: {'OK' if available else 'DOWN'}"
            env_state = "matched" if available else "mismatch/unavailable"
            remote_py = remote_py or "-"
            tooltip = f"{host}\n{message}"
            env_text = f"Env: {gui_py} ({env_state})"
            env_tooltip = f"Local: {gui_py}\nRemote: {remote_py}"
            self._view.set_ssh_status(
                available=available,
                text=status_text,
                tooltip=tooltip,
                env_text=env_text,
                env_tooltip=env_tooltip,
            )
            if show_popup:
                if available:
                    show_info_dialog(
                        title="SSH Connection Successful",
                        message=(
                            f"Beam {beam} server is reachable:\n{host}\n\n"
                            f"Using remote Python:\n{remote_py}"
                        ),
                        parent=self._view,
                    )
                else:
                    show_error_dialog(
                        title="SSH Connection Failed",
                        message=f"Could not connect to {host}.\n\n{message}",
                        parent=self._view,
                    )
            return

        # No beam context yet: check both servers and show combined state.
        host1 = self._get_ssh_host_for_beam(1)
        host2 = self._get_ssh_host_for_beam(2)
        ok1, msg1 = self._test_ssh_connection_to_host(host1)
        rt1_ok = False
        rt1_msg = "SSH unavailable"
        if ok1:
            rt1_ok, rt1_msg, _ = self._check_remote_python_runtime(host1)

        ok2, msg2 = self._test_ssh_connection_to_host(host2)
        rt2_ok = False
        rt2_msg = "SSH unavailable"
        if ok2:
            rt2_ok, rt2_msg, _ = self._check_remote_python_runtime(host2)

        available = (ok1 and rt1_ok) or (ok2 and rt2_ok)
        status_text = f"SSH: {'OK' if available else 'DOWN'}"
        tooltip = (
            f"{host1}: {'OK' if (ok1 and rt1_ok) else ('SSH OK, env mismatch' if ok1 else msg1)}\n"
            f"{host2}: {'OK' if (ok2 and rt2_ok) else ('SSH OK, env mismatch' if ok2 else msg2)}"
        )
        env_base = self._remote_python_override or sys.executable
        env_text = f"Env: {env_base} ({'matched' if available else 'checking beam-specific'})"
        env_tooltip = f"Configured Python: {env_base}"
        self._view.set_ssh_status(
            available=available,
            text=status_text,
            tooltip=tooltip,
            env_text=env_text,
            env_tooltip=env_tooltip,
        )
        if show_popup:
            lines = [
                f"{host1}: {'OK' if (ok1 and rt1_ok) else 'FAILED'}",
                f"{host2}: {'OK' if (ok2 and rt2_ok) else 'FAILED'}",
            ]
            if available:
                show_info_dialog(
                    title="SSH Connection Check",
                    message="\n".join(lines),
                    parent=self._view,
                )
            else:
                show_error_dialog(
                    title="SSH Connection Failed",
                    message="\n".join(lines + ["", rt1_msg, rt2_msg]),
                    parent=self._view,
                )

    def _run_ssh_command(
        self,
        host: str,
        remote_command: str,
        timeout_seconds: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run a command on a remote host over SSH."""
        timeout_seconds = (
            self.SSH_COMMAND_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds
        )
        try:
            result = subprocess.run(
                [
                    "ssh",
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    f"ConnectTimeout={self.SSH_CONNECT_TIMEOUT_SECONDS}",
                    "-o",
                    "ForwardX11=no",
                    "-o",
                    "ForwardX11Trusted=no",
                    host,
                    remote_command,
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            result = subprocess.CompletedProcess(
                args=exc.cmd,
                returncode=124,
                stdout=exc.stdout or "",
                stderr=f"SSH command timed out after {timeout_seconds:.0f}s",
            )
        self._log_ssh_process_output(host=host, remote_command=remote_command, result=result)
        return result

    def _run_ssh_with_stdin(
        self,
        host: str,
        remote_command: str,
        stdin_text: str,
        timeout_seconds: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run an SSH command and pass stdin text to remote process."""
        try:
            result = subprocess.run(
                [
                    "ssh",
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    f"ConnectTimeout={self.SSH_CONNECT_TIMEOUT_SECONDS}",
                    "-o",
                    "ForwardX11=no",
                    "-o",
                    "ForwardX11Trusted=no",
                    host,
                    remote_command,
                ],
                input=stdin_text,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            result = subprocess.CompletedProcess(
                args=exc.cmd,
                returncode=124,
                stdout=exc.stdout or "",
                stderr=(
                    "SSH stdin command timed out"
                    if timeout_seconds is None
                    else f"SSH stdin command timed out after {timeout_seconds:.0f}s"
                ),
            )
        self._log_ssh_process_output(host=host, remote_command=remote_command, result=result)
        return result

    def _log_ssh_process_output(
        self,
        *,
        host: str,
        remote_command: str,
        result: subprocess.CompletedProcess[str],
    ):
        """Forward SSH stdout/stderr to local logger for GUI visibility."""
        status = "ok" if result.returncode == 0 else f"failed ({result.returncode})"
        LOGGER.info("SSH %s: %s", status, host)
        LOGGER.debug("SSH command on %s: %s", host, remote_command)

        stdout_text = result.stdout.strip()
        if stdout_text:
            for line in stdout_text.splitlines():
                LOGGER.info("[ssh %s stdout] %s", host, line)

        stderr_text = result.stderr.strip()
        if stderr_text:
            log_fn = LOGGER.warning if result.returncode != 0 else LOGGER.info
            for line in stderr_text.splitlines():
                log_fn("[ssh %s stderr] %s", host, line)

    def _remote_files_exist(self, host: str, paths: list[str]) -> bool:
        """Check that all given paths exist on a remote host."""
        checks = " && ".join(f"test -f {shlex.quote(path)}" for path in paths)
        if not checks:
            return False
        result = self._run_ssh_command(host, checks)
        return result.returncode == 0

    def _resolve_sequence_file_for_ssh(
        self,
        host: str,
        beam: int,
        sequence_file: Path,
        remote_work_dir: str | None = None,
    ) -> str:
        """Return a sequence file path available on the remote host, staging if necessary."""
        sequence_path = str(sequence_file)
        if self._remote_files_exist(host, [sequence_path]):
            return sequence_path

        remote_work_dir = remote_work_dir or self._get_remote_work_dir(beam)
        mkdir_result = self._run_ssh_command(host, f"mkdir -p {shlex.quote(remote_work_dir)}")
        if mkdir_result.returncode != 0:
            stderr = mkdir_result.stderr.strip() or mkdir_result.stdout.strip() or "Unknown mkdir error"
            raise RuntimeError(f"Failed creating remote work dir on {host}: {stderr}")

        remote_sequence_path = f"{remote_work_dir}/{sequence_file.name}"
        scp_result = subprocess.run(
            [
                "scp",
                "-o",
                "BatchMode=yes",
                "-o",
                f"ConnectTimeout={self.SSH_CONNECT_TIMEOUT_SECONDS}",
                str(sequence_file),
                f"{host}:{remote_sequence_path}",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=self.SCP_COMMAND_TIMEOUT_SECONDS,
        )
        if scp_result.returncode != 0:
            stderr = scp_result.stderr.strip() or scp_result.stdout.strip() or "Unknown scp error"
            raise RuntimeError(f"Failed copying sequence file to {host}: {stderr}")

        return remote_sequence_path

    def _save_knobs_via_ssh(
        self,
        host: str,
        beam: int,
        main_magnet_knobs: dict[str, float],
        corrector_knobs: dict[str, float],
        remote_work_dir: str | None = None,
    ) -> tuple[str, str, str]:
        """Save knob dictionaries to remote files via SSH."""
        remote_work_dir = remote_work_dir or self._get_remote_work_dir(beam)
        payload = {
            "remote_work_dir": remote_work_dir,
            "magnet_knobs_filename": self.MAGNET_KNOBS_FILENAME,
            "corrector_knobs_filename": self.CORRECTOR_KNOBS_FILENAME,
            "main_magnet_knobs": main_magnet_knobs,
            "corrector_knobs": corrector_knobs,
        }
        payload_json = json.dumps(payload)
        script = (
            "import json\n"
            "from pathlib import Path\n"
            "from pymadng_utils.io import save_knobs\n"
            f"payload = json.loads({payload_json!r})\n"
            "remote_dir = Path(payload['remote_work_dir'])\n"
            "remote_dir.mkdir(parents=True, exist_ok=True)\n"
            "magnet_file = remote_dir / payload['magnet_knobs_filename']\n"
            "corrector_file = remote_dir / payload['corrector_knobs_filename']\n"
            "save_knobs(payload['main_magnet_knobs'], magnet_file)\n"
            "save_knobs(payload['corrector_knobs'], corrector_file)\n"
            "print('OMC3_GUI_KNOBS=' + json.dumps({'magnet_file': str(magnet_file), 'corrector_file': str(corrector_file), 'work_dir': str(remote_dir)}))\n"
        )
        remote_python = self._get_remote_python_executable(host)
        result = self._run_ssh_with_stdin(
            host=host,
            remote_command=f"{shlex.quote(remote_python)} -",
            stdin_text=script,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip() or "Unknown remote save error"
            raise RuntimeError(f"Remote knob save failed on {host}: {stderr}")

        marker = "OMC3_GUI_KNOBS="
        payload_line = ""
        for line in reversed(result.stdout.splitlines()):
            if line.startswith(marker):
                payload_line = line[len(marker) :]
                break
        if not payload_line:
            raise RuntimeError(f"Remote knob save on {host} returned no payload.")
        parsed = json.loads(payload_line)
        if not isinstance(parsed, dict):
            raise RuntimeError("Invalid remote knob payload type.")
        return str(parsed["work_dir"]), str(parsed["magnet_file"]), str(parsed["corrector_file"])

    @Slot()
    def _on_view_destroyed(self, *_):
        """Ensure temporary working directory is removed when window is closed."""
        self._cleanup_temp_work_dir()

    @Slot()
    def _on_select_model_dir(self):
        """Handle model directory selection."""
        dialog = OpenDirectoryDialog(
            caption="Select Model Directory",
            parent=self._view,
        )
        self._add_betabeat_shortcut(dialog)
        model_dir = dialog.run_selection_dialog()

        if model_dir:
            self._register_running_processes(1)
            try:
                origin_ctx = self._optimisation_tabs[self._active_tab_index]
                analysis_revision_at_start = self._analysis_context_revision

                beam_match = re.search(r"[Bb](\d)", str(model_dir))
                if beam_match:
                    LOGGER.info(f"Detected beam {beam_match.group(1)} from directory name")
                    beam = int(beam_match.group(1))
                else:
                    result = show_confirmation_dialog(
                        title="Beam Not Detected",
                        question="Could not detect beam number from directory name.\n\n"
                        "Is this for Beam 1?",
                        parent=self._view,
                    )
                    beam = 1 if result else 2

                temp_work_dir = self._get_temp_work_dir()
                worker_result: dict[str, object] = {}
                worker_error: Exception | None = None
                self._view.update_bottom_progress(
                    text="Loading model directory...",
                    value=0,
                    indeterminate=True,
                    visible=True,
                )
                QApplication.processEvents()

                def run_worker():
                    nonlocal worker_error
                    try:
                        model_info, accelerator, mad_interface = self._load_model_info_background(
                            model_dir=model_dir,
                            beam=beam,
                            temp_work_dir=temp_work_dir,
                        )
                        worker_result["model_info"] = model_info
                        worker_result["accelerator"] = accelerator
                        worker_result["mad_interface"] = mad_interface
                    except BaseException as exc:
                        if isinstance(exc, (SystemExit, KeyboardInterrupt)):
                            worker_error = InterruptedError("Interrupted by user.")
                            return
                        worker_error = exc

                worker = threading.Thread(target=run_worker, name="dpp-model-load-worker", daemon=True)
                worker.start()
                self._register_interrupt_thread(worker)
                hard_interrupted = False
                try:
                    while worker.is_alive():
                        self._maybe_auto_escalate_interrupt()
                        if self._interrupt_hard_event.is_set():
                            hard_interrupted = True
                            break
                        QApplication.processEvents()
                        time.sleep(0.1)
                    if not hard_interrupted:
                        worker.join()
                finally:
                    self._unregister_interrupt_thread(worker)

                if hard_interrupted and worker_error is None:
                    worker_error = InterruptedError("Interrupted by user.")
                if worker_error is not None:
                    raise worker_error

                if not any(ctx is origin_ctx for ctx in self._optimisation_tabs):
                    return

                loaded_model_info = worker_result["model_info"]
                loaded_accelerator = worker_result["accelerator"]
                loaded_mad_interface = worker_result["mad_interface"]
                origin_active = (
                    0 <= self._active_tab_index < len(self._optimisation_tabs)
                    and self._optimisation_tabs[self._active_tab_index] is origin_ctx
                )

                if origin_active:
                    self._model_info = loaded_model_info
                    self._accelerator = loaded_accelerator
                    self._mad_interface = loaded_mad_interface
                    self._refresh_model_info_in_view()
                    self._view.enable_model_energy_update(True)
                    if self._analysis_context_revision == analysis_revision_at_start:
                        self._analysis_dir = None
                        self._analysis_ini_file = None
                        self._previous_analysis_dir = None
                        self._measurement_list_model.clear()
                        self._bad_bpms = []
                        self._reset_run_artifacts()
                        self._clear_action_info_panels()
                        self._view.update_analysis_summary(self.DEFAULT_ANALYSIS_SUMMARY)
                    self._update_measurement_buttons()

                    if self._model_info is not None and self._model_info.beam is not None:
                        self._view.enable_arc_configuration(True)
                        self._arc_list_model.load_defaults(
                            self._model_info.beam,
                            bpms=self._model_info.bpms,
                        )
                        self._update_arc_info()
                        self._update_action_buttons()
                        self._refresh_ssh_status_indicator(show_popup=False)
                else:
                    origin_ctx.model_info = loaded_model_info
                    origin_ctx.arc_list_model = ArcListModel()
                    if loaded_model_info.beam is not None:
                        origin_ctx.arc_list_model.load_defaults(
                            loaded_model_info.beam,
                            bpms=loaded_model_info.bpms,
                        )
                    origin_ctx.measurement_list_model.clear()
                    self._reset_tab_run_artifacts(origin_ctx)
                    origin_ctx.analysis_dir = None
                    origin_ctx.analysis_ini_file = None
                    origin_ctx.previous_analysis_dir = None
                    origin_ctx.bad_bpms = []
                    origin_ctx.analysis_summary_text = self.DEFAULT_ANALYSIS_SUMMARY
            except InterruptedError:
                self._view.update_datafile_info("Last action: interrupted by user.")
                self._view.update_optimisation_info("Last action: interrupted by user.")
            except Exception as e:
                LOGGER.exception(f"Error loading model info: {e}")
                show_error_dialog(
                    title="Error Loading Model",
                    message=f"Failed to load model information:\n{e}",
                    parent=self._view,
                )
            finally:
                self._unregister_running_processes(1)
                self._update_action_buttons()
                self._view.clear_bottom_progress()

    @staticmethod
    def _load_model_info_background(
        *,
        model_dir: Path,
        beam: int,
        temp_work_dir: Path,
    ) -> tuple[ModelInfo, LHC, GenericMadInterface]:
        """Build model context without touching UI state (worker-thread safe)."""
        model_info = ModelInfo(model_dir=model_dir, beam=beam)

        sequence_files = list(model_dir.glob("*.seq"))
        if sequence_files:
            LOGGER.info(f"Found sequence file: {sequence_files[0]}")
            model_info.sequence_file = model_dir / sequence_files[0]
        else:
            LOGGER.info("No sequence file found, generating from MAD-X job file")
            make_madx_sequence(
                model_info.beam, model_dir, seq_outdir=temp_work_dir, beam4=beam == 2
            )
            model_info.sequence_file = temp_work_dir / f"lhcb{model_info.beam}_saved.seq"

        job_files = list(model_dir.glob("*.madx"))
        for job_file in job_files:
            LOGGER.info(f"Checking job file for beam energy: {job_file}")
            with job_file.open("r") as f:
                for line in f:
                    energy_match = re.search(r"omc3_beam_energy\s*=\s*([\d\.]+);", line)
                    if energy_match:
                        LOGGER.info(
                            f"Found beam energy in job file: {energy_match.group(1)} GeV"
                        )
                        model_info.beam_energy = float(energy_match.group(1))
                        break
            if model_info.beam_energy is not None:
                break
        if model_info.beam_energy is None:
            LOGGER.warning("Could not determine beam energy from job files, defaulting to 6.8 TeV")
            model_info.beam_energy = 6800.0

        accelerator = LHC(
            beam=model_info.beam,
            sequence_file=model_info.sequence_file,
            beam_energy=model_info.beam_energy,
            optimise_energy=True,
        )
        mad_interface = GenericMadInterface(
            accelerator=accelerator,
            bpm_pattern="^BPM",
        )
        all_bpms = mad_interface.all_bpms
        s_positions = [mad_interface.mad.MADX[bpm].at for bpm in all_bpms]
        model_info.bpms = [BpmInfo(name=bpm, s_position=s) for bpm, s in zip(all_bpms, s_positions)]
        return model_info, accelerator, mad_interface

    @Slot()
    def _on_copy_model_from_tab(self):
        """Copy loaded model and arc configuration from another optimisation tab."""
        target_idx = self._view.get_current_optimisation_tab()
        source_candidates = [
            idx
            for idx, ctx in enumerate(self._optimisation_tabs)
            if idx != target_idx and ctx.model_info is not None
        ]
        if not source_candidates:
            show_error_dialog(
                title="No Source Tab Available",
                message="No other tab has a loaded model to copy.",
                parent=self._view,
            )
            return

        labels = [self._optimisation_tabs[idx].name for idx in source_candidates]
        selected_label, ok = ask_item_dialog(
            parent=self._view,
            title="Copy Model From Tab",
            label="Source tab:",
            items=labels,
            editable=False,
        )
        if not ok:
            return

        source_idx = source_candidates[labels.index(selected_label)]
        source_ctx = self._optimisation_tabs[source_idx]
        if source_ctx.model_info is None:
            show_error_dialog(
                title="Invalid Source Tab",
                message="Selected source tab does not contain a loaded model.",
                parent=self._view,
            )
            return

        self._model_info = copy.deepcopy(source_ctx.model_info)
        self._arc_list_model = self._clone_arc_list_model(source_ctx.arc_list_model)
        self._view.set_arc_dropdown_model(self._arc_list_model)
        self._refresh_model_info_in_view()
        self._view.enable_model_energy_update(True)
        self._view.enable_arc_configuration(True)
        self._update_arc_info()
        self._update_action_buttons()
        self._capture_current_tab_context()

    def _load_model_info_with_progress(
        self,
        model_dir: Path,
        *,
        reset_analysis_state: bool,
        origin_ctx: OptimisationTabContext | None = None,
    ) -> bool:
        """Load model in background while keeping the UI responsive."""
        self._register_running_processes(1)
        try:
            if origin_ctx is None:
                if self._active_tab_index < 0 or self._active_tab_index >= len(self._optimisation_tabs):
                    return False
                origin_ctx = self._optimisation_tabs[self._active_tab_index]
            analysis_revision_at_start = origin_ctx.analysis_context_revision

            beam_match = re.search(r"[Bb](\d)", str(model_dir))
            if beam_match:
                LOGGER.info(f"Detected beam {beam_match.group(1)} from directory name")
                beam = int(beam_match.group(1))
            else:
                result = show_confirmation_dialog(
                    title="Beam Not Detected",
                    question="Could not detect beam number from directory name.\n\n"
                    "Is this for Beam 1?",
                    parent=self._view,
                )
                beam = 1 if result else 2

            temp_work_dir = self._get_temp_work_dir()
            worker_result: dict[str, object] = {}
            worker_error: Exception | None = None
            self._view.update_bottom_progress(
                text="Loading model directory...",
                value=0,
                indeterminate=True,
                visible=True,
            )
            QApplication.processEvents()

            def run_worker():
                nonlocal worker_error
                try:
                    model_info, accelerator, mad_interface = self._load_model_info_background(
                        model_dir=model_dir,
                        beam=beam,
                        temp_work_dir=temp_work_dir,
                    )
                    worker_result["model_info"] = model_info
                    worker_result["accelerator"] = accelerator
                    worker_result["mad_interface"] = mad_interface
                except BaseException as exc:
                    if isinstance(exc, (SystemExit, KeyboardInterrupt)):
                        worker_error = InterruptedError("Interrupted by user.")
                        return
                    worker_error = exc

            worker = threading.Thread(target=run_worker, name="dpp-model-load-worker", daemon=True)
            worker.start()
            self._register_interrupt_thread(worker)
            hard_interrupted = False
            try:
                while worker.is_alive():
                    self._maybe_auto_escalate_interrupt()
                    if self._interrupt_hard_event.is_set():
                        hard_interrupted = True
                        break
                    QApplication.processEvents()
                    time.sleep(0.1)
                if not hard_interrupted:
                    worker.join()
            finally:
                self._unregister_interrupt_thread(worker)

            if hard_interrupted and worker_error is None:
                worker_error = InterruptedError("Interrupted by user.")
            if worker_error is not None:
                raise worker_error

            if not any(ctx is origin_ctx for ctx in self._optimisation_tabs):
                return False

            loaded_model_info = worker_result["model_info"]
            loaded_accelerator = worker_result["accelerator"]
            loaded_mad_interface = worker_result["mad_interface"]
            origin_active = (
                0 <= self._active_tab_index < len(self._optimisation_tabs)
                and self._optimisation_tabs[self._active_tab_index] is origin_ctx
            )

            if origin_active:
                self._model_info = loaded_model_info
                self._accelerator = loaded_accelerator
                self._mad_interface = loaded_mad_interface
                self._refresh_model_info_in_view()
                self._view.enable_model_energy_update(True)
                self._reset_run_artifacts()
                self._clear_action_info_panels()

                if reset_analysis_state and self._analysis_context_revision == analysis_revision_at_start:
                    self._analysis_dir = None
                    self._analysis_ini_file = None
                    self._previous_analysis_dir = None
                    self._measurement_list_model.clear()
                    self._bad_bpms = []
                    self._view.update_analysis_summary(self.DEFAULT_ANALYSIS_SUMMARY)
                self._update_measurement_buttons()

                if self._model_info is not None and self._model_info.beam is not None:
                    self._view.enable_arc_configuration(True)
                    self._arc_list_model.load_defaults(
                        self._model_info.beam,
                        bpms=self._model_info.bpms,
                    )
                    self._update_arc_info()
                    self._refresh_ssh_status_indicator(show_popup=False)
            else:
                origin_ctx.model_info = loaded_model_info
                origin_ctx.arc_list_model = ArcListModel()
                if loaded_model_info.beam is not None:
                    origin_ctx.arc_list_model.load_defaults(
                        loaded_model_info.beam,
                        bpms=loaded_model_info.bpms,
                    )
                self._reset_tab_run_artifacts(origin_ctx)
                if reset_analysis_state and origin_ctx.analysis_context_revision == analysis_revision_at_start:
                    origin_ctx.analysis_dir = None
                    origin_ctx.analysis_ini_file = None
                    origin_ctx.previous_analysis_dir = None
                    origin_ctx.measurement_list_model.clear()
                    origin_ctx.bad_bpms = []
                    origin_ctx.analysis_summary_text = self.DEFAULT_ANALYSIS_SUMMARY

            return True
        except InterruptedError:
            self._view.update_datafile_info("Last action: interrupted by user.")
            self._view.update_optimisation_info("Last action: interrupted by user.")
        except Exception as e:
            LOGGER.exception(f"Error loading model info: {e}")
            show_error_dialog(
                title="Error Loading Model",
                message=f"Failed to load model information:\n{e}",
                parent=self._view,
            )
        finally:
            self._unregister_running_processes(1)
            self._update_action_buttons()
            self._view.clear_bottom_progress()
        return False

    def _load_model_info(self, model_dir: Path):
        """Load model information from directory."""
        try:
            self._model_info = ModelInfo(model_dir=model_dir)

            # Try to extract beam from directory name
            beam_match = re.search(r"[Bb](\d)", str(model_dir))
            if beam_match:
                LOGGER.info(f"Detected beam {beam_match.group(1)} from directory name")
                beam = int(beam_match.group(1))
                self._model_info.beam = beam
            else:
                # Create a dialog to ask user for beam number
                result = show_confirmation_dialog(
                    title="Beam Not Detected",
                    question="Could not detect beam number from directory name.\n\n"
                    "Is this for Beam 1?",
                    parent=self._view,
                )
                self._model_info.beam = 1 if result else 2

            # Look for sequence file
            sequence_files = list(model_dir.glob("*.seq"))
            if sequence_files:
                LOGGER.info(f"Found sequence file: {sequence_files[0]}")
                self._model_info.sequence_file = model_dir / sequence_files[0]
            else:
                LOGGER.info("No sequence file found, generating from MAD-X job file")
                temp_work_dir = self._get_temp_work_dir()
                # Create the sequence file from the model.
                make_madx_sequence(self._model_info.beam, model_dir, seq_outdir=temp_work_dir)
                # Now we know the madx file is lhcb[beam]_saved.seq
                self._model_info.sequence_file = (
                    temp_work_dir / f"lhcb{self._model_info.beam}_saved.seq"
                )

            # Read the job create nominal file to determine the beam energy
            job_files = list(model_dir.glob("*.madx"))
            for job_file in job_files:
                LOGGER.info(f"Checking job file for beam energy: {job_file}")
                with job_file.open("r") as f:
                    for line in f:
                        energy_match = re.search(r"omc3_beam_energy\s*=\s*([\d\.]+);", line)
                        if energy_match:
                            LOGGER.info(
                                f"Found beam energy in job file: {energy_match.group(1)} GeV"
                            )
                            self._model_info.beam_energy = float(energy_match.group(1))
                            break
                if self._model_info.beam_energy is not None:
                    break
            if self._model_info.beam_energy is None:
                LOGGER.warning(
                    "Could not determine beam energy from job files, defaulting to 6.8 TeV"
                )
                self._model_info.beam_energy = 6800.0  # Default to 6.8 TeV if not found

            self._initialise_mad_interface()
            self._refresh_model_info_in_view()
            self._view.enable_model_energy_update(True)
            self._analysis_dir = None
            self._analysis_ini_file = None
            self._previous_analysis_dir = None
            self._measurement_list_model.clear()
            self._bad_bpms = []
            self._reset_run_artifacts()
            self._clear_action_info_panels()
            self._view.update_analysis_summary(self.DEFAULT_ANALYSIS_SUMMARY)
            self._update_measurement_buttons()

            # Enable arc configuration if beam is known
            if self._model_info.beam is not None:
                self._view.enable_arc_configuration(True)
                # Load default arcs
                self._arc_list_model.load_defaults(
                    self._model_info.beam,
                    bpms=self._model_info.bpms,
                )
                self._update_arc_info()
                self._update_action_buttons()
                self._refresh_ssh_status_indicator(show_popup=False)

        except Exception as e:
            LOGGER.exception(f"Error loading model info: {e}")
            show_error_dialog(
                title="Error Loading Model",
                message=f"Failed to load model information:\n{e}",
                parent=self._view,
            )

    def _initialise_mad_interface(self):
        """Create accelerator and MAD interface from current model information."""
        model_info, beam, sequence_file, beam_energy = self._require_loaded_model_context()
        self._accelerator = LHC(
            beam=beam,
            sequence_file=sequence_file,
            beam_energy=beam_energy,
            optimise_energy=True,
        )
        self._mad_interface = GenericMadInterface(
            accelerator=self._accelerator,
            bpm_pattern="^BPM",
        )

        all_bpms = self._mad_interface.all_bpms
        s_positions = [self._mad_interface.mad.MADX[bpm].at for bpm in all_bpms]
        model_info.bpms = [BpmInfo(name=bpm, s_position=s) for bpm, s in zip(all_bpms, s_positions)]

    def _refresh_model_info_in_view(self):
        """Push model metadata to the view."""
        model_info, beam, sequence_file, beam_energy = self._require_loaded_model_context()
        self._view.set_model_info(
            model_dir=str(model_info.model_dir),
            beam=beam,
            sequence_file=sequence_file.name,
            beam_energy=beam_energy,
            num_bpms=len(model_info.bpms),
        )

    def _require_loaded_model_context(self) -> tuple[ModelInfo, int, Path, float]:
        """Return loaded model data with non-optional types for static checking."""
        model_info = self._model_info
        if (
            model_info is None
            or model_info.beam is None
            or model_info.sequence_file is None
            or model_info.beam_energy is None
        ):
            raise RuntimeError(
                "Model information is incomplete. Please select a valid model directory."
            )

        return model_info, model_info.beam, model_info.sequence_file, model_info.beam_energy

    def _apply_model_energy(self, new_energy: float):
        """Apply a beam energy update to the model and dependent arc metadata."""
        if self._model_info is None:
            raise RuntimeError("Model must be loaded before updating beam energy.")

        self._model_info.beam_energy = float(new_energy)
        self._initialise_mad_interface()
        self._refresh_model_info_in_view()

        bpm_s_positions = {bpm.name: bpm.s_position for bpm in self._model_info.bpms}
        for index, arc in enumerate(self._arc_list_model.get_all_arcs()):
            arc.magnet_range_start_s = bpm_s_positions.get(arc.magnet_range_start_bpm, 0.0)
            arc.magnet_range_end_s = bpm_s_positions.get(arc.magnet_range_end_bpm, 0.0)
            self._arc_list_model.update_arc(index, arc)
        self._update_arc_info()

    @Slot()
    def _on_update_model_energy(self):
        """Handle model energy update button click."""
        if not self._model_info or self._model_info.beam is None:
            show_error_dialog(
                title="No Model Selected",
                message="Please select a model directory first.",
                parent=self._view,
            )
            return

        current_energy = self._model_info.beam_energy or 6800.0
        new_energy, ok = ask_double_dialog(
            parent=self._view,
            title="Update Beam Energy",
            label="Beam Energy (GeV):",
            value=current_energy,
            min_value=0.0,
            max_value=1_000_000.0,
            decimals=3,
        )
        if not ok:
            return

        if abs(new_energy - current_energy) < 1e-9:
            return

        try:
            self._apply_model_energy(new_energy)

            show_info_dialog(
                title="Model Energy Updated",
                message=f"Beam energy updated to {new_energy:.3f} GeV.",
                parent=self._view,
            )
        except Exception as e:
            LOGGER.exception(f"Error updating model energy: {e}")
            show_error_dialog(
                title="Error Updating Model Energy",
                message=f"Failed to update model energy:\n{e}",
                parent=self._view,
            )

    @Slot()
    def _on_configure_arcs(self):
        """Handle arc configuration button click."""
        if not self._model_info or not self._model_info.beam:
            show_error_dialog(
                title="No Model Selected",
                message="Please select a model directory first.",
                parent=self._view,
            )
            return

        # Get current arc
        current_arc_index = self._view.get_selected_arc_index()
        if current_arc_index < 0:
            show_error_dialog(
                title="No Arc Selected",
                message="Please select an arc to configure.",
                parent=self._view,
            )
            return

        current_arc = self._arc_list_model.get_arc(current_arc_index)

        # Show configuration dialog
        dialog = ArcConfigDialog(
            arc_config=current_arc,
            bpms=self._model_info.bpms,
            parent=self._view,
        )

        if dialog.exec_():
            updated_arc = dialog.get_arc_config()
            self._arc_list_model.update_arc(current_arc_index, updated_arc)
            self._update_arc_info()

    @Slot()
    def _on_select_analysis_dir(self):
        """Handle analysis directory selection."""
        if self._active_tab_index < 0 or self._active_tab_index >= len(self._optimisation_tabs):
            return
        origin_ctx = self._optimisation_tabs[self._active_tab_index]
        start_dir = self._get_measurement_dialog_start_dir()
        dialog = OpenDirectoryDialog(
            caption="Select Analysis Directory",
            directory=start_dir,
            parent=self._view,
        )
        self._add_betabeat_shortcut(dialog)
        analysis_dir = dialog.run_selection_dialog()
        if analysis_dir is None:
            return

        try:
            (
                ini_file,
                measurement_files,
                bad_bpms,
                missing_count,
                analysis_model_dir,
            ) = self._read_analysis_context(analysis_dir)
        except Exception as e:
            LOGGER.exception("Failed to load analysis directory: %s", e)
            show_error_dialog(
                title="Invalid Analysis Directory",
                message=f"Failed to load analysis information:\n{e}",
                parent=self._view,
            )
            return

        loaded_model_info = self._model_info
        if loaded_model_info is None:
            if analysis_model_dir is None:
                show_error_dialog(
                    title="Model Required",
                    message=(
                        "No model is currently loaded, and the analysis ini has no 'model_dir' entry.\n"
                        "Please load a model directory first."
                    ),
                    parent=self._view,
                )
                return
            if not analysis_model_dir.exists():
                show_error_dialog(
                    title="Invalid Model Directory",
                    message=(
                        "The analysis ini references a model directory that does not exist:\n"
                        f"{analysis_model_dir}"
                    ),
                    parent=self._view,
                )
                return
            if not self._load_model_info_with_progress(
                analysis_model_dir,
                reset_analysis_state=False,
                origin_ctx=origin_ctx,
            ):
                return
        elif analysis_model_dir is not None:
            loaded_model_dir = loaded_model_info.model_dir.expanduser().resolve(strict=False)
            if loaded_model_dir != analysis_model_dir:
                switch_model = show_confirmation_dialog(
                    title="Model Directory Mismatch",
                    question=(
                        "The analysis directory references a different model directory than the one currently loaded.\n\n"
                        "Press OK to reload the model directory that ran the analysis.\n"
                        "Press Cancel to continue using the currently loaded model directory.\n\n"
                        f"Analysis model: {analysis_model_dir}\n"
                        f"Current model: {loaded_model_dir}"
                    ),
                    parent=self._view,
                )
                if switch_model:
                    if not analysis_model_dir.exists():
                        show_error_dialog(
                            title="Invalid Model Directory",
                            message=(
                                "The analysis ini references a model directory that does not exist:\n"
                                f"{analysis_model_dir}"
                            ),
                            parent=self._view,
                        )
                        return
                    if not self._load_model_info_with_progress(
                        analysis_model_dir,
                        reset_analysis_state=False,
                        origin_ctx=origin_ctx,
                    ):
                        return

        summary_lines = [
            f"<b>Analysis directory:</b> {analysis_dir}",
            f"<b>Analysis ini:</b> {ini_file.name if ini_file is not None else 'N/A'}",
            f"<b>Loaded measurement files:</b> {len(measurement_files)}",
            f"<b>Bad BPMs:</b> {len(bad_bpms)}",
        ]
        if missing_count:
            summary_lines.append(f"<b>Missing files skipped:</b> {missing_count}")
        summary_text = "<br><br>".join(summary_lines)

        if not any(ctx is origin_ctx for ctx in self._optimisation_tabs):
            return
        origin_active = (
            0 <= self._active_tab_index < len(self._optimisation_tabs)
            and self._optimisation_tabs[self._active_tab_index] is origin_ctx
        )

        if origin_active:
            self._analysis_dir = analysis_dir
            self._analysis_ini_file = ini_file
            self._previous_analysis_dir = analysis_dir
            self._bad_bpms = sorted(bad_bpms)
            self._analysis_context_revision += 1
            self._measurement_list_model.clear()
            self._measurement_list_model.add_files(measurement_files)
            self._reset_run_artifacts()
            self._clear_action_info_panels()
            self._view.update_analysis_summary(summary_text)
            self._update_measurement_buttons()
            self._update_action_buttons()
        else:
            origin_ctx.analysis_dir = analysis_dir
            origin_ctx.analysis_ini_file = ini_file
            origin_ctx.previous_analysis_dir = analysis_dir
            origin_ctx.bad_bpms = sorted(bad_bpms)
            origin_ctx.analysis_context_revision += 1
            origin_ctx.measurement_list_model.clear()
            origin_ctx.measurement_list_model.add_files(measurement_files)
            self._reset_tab_run_artifacts(origin_ctx)
            origin_ctx.analysis_summary_text = summary_text

    @Slot()
    def _on_select_measurement_files(self):
        """Handle measurement file selection."""
        if self._analysis_dir is None:
            show_error_dialog(
                title="Analysis Required",
                message="Please select an analysis directory first.",
                parent=self._view,
            )
            return
        start_dir = self._get_measurement_dialog_start_dir()
        dialog = OpenFilesDialog(
            caption="Select Measurement Files",
            filter="SDDS Files (*.sdds);;All Files (*)",
            directory=start_dir,
            parent=self._view,
        )
        self._add_betabeat_shortcut(dialog)

        files = dialog.run_selection_dialog()
        if files:
            self._measurement_list_model.add_files(files)
            self._update_action_buttons()

    @Slot()
    def _on_select_measurement_folders(self):
        """Handle measurement folder selection."""
        if self._analysis_dir is None:
            show_error_dialog(
                title="Analysis Required",
                message="Please select an analysis directory first.",
                parent=self._view,
            )
            return
        start_dir = self._get_measurement_dialog_start_dir()
        dialog = OpenDirectoriesDialog(
            caption="Select Measurement Folders",
            directory=start_dir,
            parent=self._view,
        )
        self._add_betabeat_shortcut(dialog)

        folders = dialog.run_selection_dialog()
        if folders:
            self._measurement_list_model.add_folders(folders)
            self._bad_bpms = sorted(set(self._bad_bpms).union(self.find_bad_bpms(folders)))
            self._update_action_buttons()

    def _read_analysis_context(
        self, optics_folder: Path
    ) -> tuple[Path, list[Path], set[str], int, Path | None]:
        """Read analysis ini and return measurements, bad BPMs, and model_dir."""
        ini_files = list(optics_folder.glob("analysis*.ini"))
        if not ini_files:
            raise FileNotFoundError(f"No analysis*.ini file found in {optics_folder}")
        ini_file = ini_files[0]

        config = configparser.ConfigParser()
        config.read(ini_file)
        model_dir = self._extract_model_dir_from_analysis_ini(config, ini_file)
        files_str = config["DEFAULT"].get("files") if "DEFAULT" in config else None
        if not files_str:
            raise ValueError(f"No 'files' entry in {ini_file}")

        try:
            file_paths = ast.literal_eval(files_str)
        except (ValueError, SyntaxError) as exc:
            raise ValueError(f"Failed to parse files list in {ini_file}: {exc}") from exc

        measurement_files = [Path(file_path) for file_path in file_paths]
        resolved_measurements = self._resolve_measurement_files(measurement_files)
        existing_measurements = [path for path in resolved_measurements if path.exists()]
        if not existing_measurements:
            raise FileNotFoundError(
                f"Analysis {ini_file} contains no existing measurement files."
            )
        missing_count = max(len(resolved_measurements) - len(existing_measurements), 0)

        bad_bpms = self._find_all_bad_bpms_from_analysis(optics_folder)
        return ini_file, existing_measurements, bad_bpms, missing_count, model_dir

    def _extract_model_dir_from_analysis_ini(
        self, config: configparser.ConfigParser, ini_file: Path
    ) -> Path | None:
        """Extract and normalize model_dir entry from analysis ini, if present."""
        model_dir_raw = config["DEFAULT"].get("model_dir") if "DEFAULT" in config else None
        if not model_dir_raw:
            for section in config.sections():
                model_dir_raw = config[section].get("model_dir")
                if model_dir_raw:
                    break
        if not model_dir_raw:
            return None

        normalized = model_dir_raw.strip().strip("'\"")
        if not normalized:
            return None

        model_dir = Path(os.path.expandvars(normalized)).expanduser()
        if not model_dir.is_absolute():
            model_dir = (ini_file.parent / model_dir).resolve(strict=False)
        else:
            model_dir = model_dir.resolve(strict=False)
        return model_dir

    def _resolve_measurement_files(self, entries: list[Path]) -> list[Path]:
        """Resolve analysis ini entries to unique raw measurement file paths."""
        resolved: list[Path] = []
        seen: set[Path] = set()

        for entry in entries:
            candidates = [entry]

            # Optics analysis often stores files as "...sdds_bunchID<id>".
            # Convert those back to the raw SDDS file path.
            entry_str = str(entry)
            candidate_str = re.sub(r"\.sdds_bunchID\d+$", ".sdds", entry_str)
            if candidate_str != entry_str:
                candidates.append(Path(candidate_str))

            # Generic fallback for "..._bunchID<id>" pattern.
            candidate_str_generic = re.sub(r"_bunchID\d+$", "", entry_str)
            if candidate_str_generic != entry_str:
                candidates.append(Path(candidate_str_generic))

            chosen = next((cand for cand in candidates if cand.exists()), candidates[-1])
            if chosen not in seen:
                seen.add(chosen)
                resolved.append(chosen)

        return resolved

    def _load_bad_bpms_from_measurement_folder(self, folder: Path) -> set[str]:
        """Load bad BPM names from one measurement folder."""
        bad_bpms: set[str] = set()
        for filepath in folder.rglob("*.bad_bpms_*"):
            with filepath.open("r") as file:
                bad_bpms.update(line.split(" ")[0] for line in file.readlines())
        bad_bpms_file = folder / "bad_bpms.txt"
        if bad_bpms_file.exists():
            with bad_bpms_file.open("r") as file:
                bad_bpms.update(line.strip() for line in file.readlines() if line.strip())
        return bad_bpms

    def _find_all_bad_bpms_from_analysis(self, optics_folder: Path) -> set[str]:
        """Find bad BPMs using analysis*.ini and linked measurement folders."""
        ini_files = list(optics_folder.glob("analysis*.ini"))
        if not ini_files:
            LOGGER.warning("No analysis*.ini file found in %s", optics_folder)
            return set()

        ini_file = ini_files[0]
        LOGGER.info("Found analysis ini file: %s", ini_file)

        config = configparser.ConfigParser()
        config.read(ini_file)
        files_str = config["DEFAULT"].get("files") if "DEFAULT" in config else None
        if not files_str:
            LOGGER.warning("No 'files' entry in %s", ini_file)
            return set()

        try:
            file_paths = ast.literal_eval(files_str)
        except (ValueError, SyntaxError) as exc:
            LOGGER.warning(
                "Failed to parse files list in %s: %s",
                ini_file,
                exc,
            )
            return set()

        measurement_folders = {Path(file_path).parent for file_path in file_paths}
        LOGGER.info("Found %d unique measurement folders", len(measurement_folders))

        all_bad_bpms: set[str] = set()
        for folder in measurement_folders:
            if folder.exists():
                folder_bad_bpms = self._load_bad_bpms_from_measurement_folder(folder)
                all_bad_bpms.update(folder_bad_bpms)
                LOGGER.debug("Found %d bad BPMs in %s", len(folder_bad_bpms), folder)
            else:
                LOGGER.warning("Measurement folder does not exist: %s", folder)

        LOGGER.info("Total unique bad BPMs found: %d", len(all_bad_bpms))
        return all_bad_bpms

    def find_bad_bpms(self, measurement_dirs: list[Path]) -> list[str]:
        """Find bad BPM names from measurement folders."""
        LOGGER.info(
            "find_bad_bpms called with %d measurement folders",
            len(measurement_dirs),
        )
        bad_bpms: set[str] = set()
        for meas_dir in measurement_dirs:
            bad_bpms.update(self._load_bad_bpms_from_measurement_folder(meas_dir))
        LOGGER.info("Found %d unique bad BPMs across selected measurement folders", len(bad_bpms))
        return list(bad_bpms)

    @Slot()
    def _on_remove_measurement_file(self):
        """Handle measurement file removal."""
        if self._analysis_dir is None:
            show_error_dialog(
                title="Analysis Required",
                message="Please select an analysis directory first.",
                parent=self._view,
            )
            return
        index = self._view.get_selected_measurement_index()
        if index >= 0:
            self._measurement_list_model.remove_file(index)
            self._update_action_buttons()

    @Slot()
    def _on_configure_optimizer(self):
        """Handle optimizer configuration button click."""
        dialog = OptimizerSettingsDialog(
            config=self._optimizer_config,
            parent=self._view,
        )

        if dialog.exec_():
            self._optimizer_config = dialog.get_config()
            LOGGER.info("Optimizer configuration updated")

    @Slot()
    def _on_test_ssh_connection(self):
        """Handle test SSH connection button click."""
        self._refresh_ssh_status_indicator(show_popup=True)

    def _build_dict_from_nxcal_result(self, result: list[NXCALSResult]) -> dict[str, float]:
        """Convert NXCALSResult to a dictionary of magnet strengths."""
        return preparation_service.build_dict_from_nxcal_result(result)

    def _update_knob_files_summary(
        self,
        main_magnet_knobs: dict[str, float],
        corrector_knobs: dict[str, float],
    ):
        """Push knob file count and location details to the view."""
        preparation_service.update_knob_files_summary(self, main_magnet_knobs, corrector_knobs)

    @Slot()
    def _on_download_knobs(self):
        """Handle download knobs button click."""
        return preparation_service.on_download_knobs(self)

    @Slot()
    def _on_create_datafile(self):
        """Handle create datafile button click."""
        return preparation_service.on_create_datafile(self)

    def _create_datafile_locally(
        self,
        beam: int,
        measurement_files: list[Path],
        analysis_dir: Path,
        bad_bpms: list[str],
        output_path: Path,
        set_step,
    ) -> dict[str, object]:
        """Create the datafile locally and return summary fields."""
        return preparation_service.create_datafile_locally(
            self, beam, measurement_files, analysis_dir, bad_bpms, output_path, set_step
        )

    def _create_datafile_via_ssh(
        self,
        host: str,
        beam: int,
        sequence_file: Path,
        beam_energy: float,
        measurement_files: list[Path],
        analysis_dir: Path,
        bad_bpms: list[str],
        output_path: Path,
    ) -> dict[str, object]:
        """Create the datafile on a remote host through SSH."""
        return preparation_service.create_datafile_via_ssh(
            self, host, beam, sequence_file, beam_energy, measurement_files, analysis_dir, bad_bpms, output_path
        )

    def _download_knobs_locally_worker(
        self,
        beam: int,
        meas_time: pd.Timestamp,
    ) -> dict[str, object]:
        """Download knobs locally and save files in temp work dir."""
        return preparation_service.download_knobs_locally_worker(
            self,
            beam,
            meas_time,
            self._get_magnet_knobs_file(),
            self._get_corrector_knobs_file(),
        )

    def _create_datafile_worker(
        self,
        beam: int,
        sequence_file: Path,
        beam_energy: float,
        measurement_files: list[Path],
        analysis_dir: Path,
        bad_bpms: list[str],
        output_path: Path,
    ) -> dict[str, object]:
        """Create datafile, preferring SSH and falling back to local."""
        return preparation_service.create_datafile_worker(
            self,
            beam,
            sequence_file,
            beam_energy,
            measurement_files,
            analysis_dir,
            bad_bpms,
            output_path,
        )

    @Slot()
    def _on_prepare_inputs_parallel(self):
        """Run knob download and datafile creation in parallel."""
        return preparation_service.on_prepare_inputs_parallel(self)

    def _build_optimisation_range_config(self, beam: int):
        """Create optimise_ranges-compatible range config from GUI arc settings."""
        return optimisation_service.build_optimisation_range_config(self, beam)

    @staticmethod
    def _compute_weighted_mean_and_variance(
        sub: pd.DataFrame,
        value_col: str,
        var_col: str,
    ) -> tuple[float, float]:
        """Compute inverse-variance weighted mean and variance of mean."""
        return preparation_service.compute_weighted_mean_and_variance(sub, value_col, var_col)

    def _make_aba_config_objects(self):
        """Translate GUI config dataclasses to aba_optimiser config objects."""
        return optimisation_service.make_aba_config_objects(self)

    @staticmethod
    def _weighted_mean(values: list[float], uncertainties: list[float]) -> float | None:
        """Compute weighted mean with 1/sigma^2 weights."""
        return optimisation_service.weighted_mean(values, uncertainties)

    def _copy_file_to_remote(self, host: str, local_path: Path, remote_path: str):
        """Copy local file to remote path via SCP."""
        return optimisation_service.copy_file_to_remote(self, host, local_path, remote_path)

    def _resolve_file_for_remote_optimisation(
        self,
        *,
        host: str,
        beam: int,
        local_path: Path | None,
        remote_path: str | None,
        default_filename: str,
    ) -> str:
        """Resolve remote path for optimisation input file, copying from local when needed."""
        return optimisation_service.resolve_file_for_remote_optimisation(
            self,
            host=host,
            beam=beam,
            local_path=local_path,
            remote_path=remote_path,
            default_filename=default_filename,
        )

    def _run_optimisation_locally(
        self,
        *,
        beam: int,
        energy: float,
        sequence_file: Path,
        magnet_knobs_file: Path,
        corrector_knobs_file: Path,
        measurement_file: Path,
        bad_bpms: list[str],
    ) -> dict[str, object]:
        """Run optimisation in local process."""
        return optimisation_service.run_optimisation_locally(
            self,
            beam=beam,
            energy=energy,
            sequence_file=sequence_file,
            magnet_knobs_file=magnet_knobs_file,
            corrector_knobs_file=corrector_knobs_file,
            measurement_file=measurement_file,
            bad_bpms=bad_bpms,
        )

    def _run_optimisation_via_ssh(
        self,
        *,
        host: str,
        beam: int,
        energy: float,
        sequence_file: str,
        magnet_knobs_file: str,
        corrector_knobs_file: str,
        measurement_file: str,
        bad_bpms: list[str],
    ) -> dict[str, object]:
        """Run optimisation on remote host and return parsed payload."""
        return optimisation_service.run_optimisation_via_ssh(
            self,
            host=host,
            beam=beam,
            energy=energy,
            sequence_file=sequence_file,
            magnet_knobs_file=magnet_knobs_file,
            corrector_knobs_file=corrector_knobs_file,
            measurement_file=measurement_file,
            bad_bpms=bad_bpms,
        )

    @Slot()
    def _on_run_optimisation(self):
        """Handle run optimisation button click."""
        return optimisation_service.on_run_optimisation(self)

    @Slot()
    def _on_add_optimisation_tab(self):
        """Create a new optimisation tab context."""
        self._capture_current_tab_context()
        next_idx = len(self._optimisation_tabs) + 1
        name = f"Optimisation {next_idx}"
        self._optimisation_tabs.append(OptimisationTabContext(name=name))
        new_index = self._view.add_optimisation_tab(name)
        self._view.set_current_optimisation_tab(new_index, emit_signal=False)
        self._apply_tab_context(new_index)

    @Slot()
    def _on_close_optimisation_tab(self):
        """Close active optimisation tab and switch to neighbour."""
        self._close_optimisation_tab(self._view.get_current_optimisation_tab())

    @Slot(int)
    def _on_close_optimisation_tab_at(self, idx: int):
        """Close optimisation tab at provided index."""
        self._close_optimisation_tab(idx)

    def _close_optimisation_tab(self, idx: int):
        """Close one optimisation tab and switch context safely."""
        if self._view.get_optimisation_tab_count() <= 1:
            show_error_dialog(
                title="Cannot Close Tab",
                message="At least one optimisation tab must remain open.",
                parent=self._view,
            )
            return
        if idx < 0 or idx >= len(self._optimisation_tabs):
            return

        tab_name = self._view.get_optimisation_tab_label(idx)
        confirmed = show_confirmation_dialog(
            title="Delete Optimisation Tab",
            question=f"Delete tab '{tab_name}'?\nThis cannot be undone.",
            parent=self._view,
        )
        if not confirmed:
            return
        self._capture_current_tab_context()
        closing_ctx = self._optimisation_tabs[idx]
        if closing_ctx.temp_work_dir is not None:
            try:
                closing_ctx.temp_work_dir.cleanup()
            except Exception:
                LOGGER.warning("Failed to cleanup tab temporary directory", exc_info=True)
            closing_ctx.temp_work_dir = None
        self._view.remove_optimisation_tab(idx)
        del self._optimisation_tabs[idx]
        next_idx = min(idx, self._view.get_optimisation_tab_count() - 1)
        self._view.set_current_optimisation_tab(next_idx, emit_signal=False)
        self._apply_tab_context(next_idx)

    @Slot(int)
    def _on_rename_optimisation_tab(self, idx: int):
        """Rename one optimisation tab."""
        if idx < 0 or idx >= len(self._optimisation_tabs):
            return
        current = self._view.get_optimisation_tab_label(idx)
        new_name, ok = ask_text_dialog(
            parent=self._view,
            title="Rename Optimisation Tab",
            label="Tab name:",
            text=current,
        )
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name:
            return
        self._optimisation_tabs[idx].name = new_name
        self._view.rename_optimisation_tab(idx, new_name)

    @Slot(int)
    def _on_optimisation_tab_changed(self, idx: int):
        """Switch active optimisation context."""
        if idx < 0 or idx >= len(self._optimisation_tabs):
            return
        if idx == self._active_tab_index:
            return
        self._capture_current_tab_context()
        self._apply_tab_context(idx)

    @Slot()
    def _on_set_env(self):
        """Set or clear preferred remote Python executable."""
        current = self._remote_python_override or ""
        new_env, ok = ask_text_dialog(
            parent=self._view,
            title="Set Remote Python Environment",
            label="Remote Python executable path (leave empty to use local executable):",
            text=current,
        )
        if not ok:
            return
        self._remote_python_override = new_env.strip() or None
        self._refresh_ssh_status_indicator(show_popup=False)

    @Slot()
    def _on_save_results(self):
        """Copy the latest optimisation results file to a user-selected location."""
        if self._optimisation_results_file is None or not self._optimisation_results_file.exists():
            show_error_dialog(
                title="No Results Available",
                message="Run optimisation first to produce results.",
                parent=self._view,
            )
            return

        start_dir = self._analysis_dir if self._analysis_dir is not None else self._optimisation_results_file.parent
        default_path = start_dir / self._optimisation_results_file.name
        dialog = SaveFileDialog(
            parent=self._view,
            caption="Save Results As",
            directory=default_path,
            filter="Text Files (*.txt);;All Files (*)",
            default_suffix="txt",
        )
        destination = dialog.run_selection_dialog()
        if destination is None:
            return

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self._optimisation_results_file, destination)
            show_info_dialog(
                title="Results Saved",
                message=f"Saved optimisation results to:\n{destination}",
                parent=self._view,
            )
        except Exception as exc:
            LOGGER.exception("Failed to save optimisation results: %s", exc)
            show_error_dialog(
                title="Save Failed",
                message=f"Could not save results:\n{exc}",
                parent=self._view,
            )

    @Slot()
    def _on_view_results(self):
        """Display plot with selectable tab overlays (default: current tab only)."""
        self._capture_current_tab_context()
        available_tabs = [
            idx
            for idx, ctx in enumerate(self._optimisation_tabs)
            if (
                (ctx.optimisation_results_file is not None and ctx.optimisation_results_file.exists())
                or ctx.latest_deltap_wrt_ref_results
            )
        ]
        if not available_tabs:
            show_error_dialog(
                title="No Results Available",
                message="Run optimisation first to view results.",
                parent=self._view,
            )
            return

        initial_tab_index = (
            self._active_tab_index
            if self._active_tab_index in available_tabs
            else available_tabs[0]
        )
        initial_parsed = self._read_deltap_results_for_context(
            self._optimisation_tabs[initial_tab_index]
        )
        ref_energy = float(initial_parsed["ref_energy"])

        class _DeltaPAxisItem(pg.AxisItem):
            def tickStrings(self, values, scale, spacing):
                return [DppOptimisationController._format_deltap_value(value) for value in values]

        dialog = QtWidgets.QDialog(self._view)
        dialog.setWindowTitle(f"Delta-p (w.r.t. {int(ref_energy)} GeV) vs Arc")
        dialog.resize(1100, 620)
        layout = QtWidgets.QHBoxLayout(dialog)

        selector = QtWidgets.QListWidget()
        selector.setMinimumWidth(240)
        selector.setMaximumWidth(360)
        selector.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        selector.setStyleSheet(styles.list_widget_text_style())
        for idx in available_tabs:
            name = self._optimisation_tabs[idx].name
            item = QtWidgets.QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            default_checked = idx == self._active_tab_index
            item.setCheckState(Qt.Checked if default_checked else Qt.Unchecked)
            item.setData(Qt.UserRole, idx)
            selector.addItem(item)
        sidebar_layout = QtWidgets.QVBoxLayout()
        sidebar_layout.addWidget(selector, 1)
        info_table = QtWidgets.QTableWidget()
        self._configure_results_info_table(info_table)
        sidebar_layout.addWidget(info_table, 1)
        layout.addLayout(sidebar_layout, 0)

        plot = pg.PlotWidget(axisItems={"left": _DeltaPAxisItem(orientation="left")})
        self._configure_results_plot(plot, ref_energy)
        layout.addWidget(plot, 1)

        color_cycle = colors.PLOT_SERIES_COLORS

        def redraw_plot():
            plot.clear()
            plot.addLegend(labelTextColor=colors.TEXT_DARK)
            selected_indices: list[int] = []
            for row in range(selector.count()):
                item = selector.item(row)
                if item.checkState() == Qt.Checked:
                    selected_indices.append(int(item.data(Qt.UserRole)))

            if not selected_indices:
                plot.setTitle("Select one or more tabs to view results.")
                info_table.setRowCount(0)
                return

            title_ref_energy = ref_energy
            table_rows: list[tuple[str, str, str, str]] = []
            for i, tab_index in enumerate(selected_indices):
                tab_ctx = self._optimisation_tabs[tab_index]
                parsed = self._read_deltap_results_for_context(tab_ctx)
                title_ref_energy = float(parsed["ref_energy"])
                y_values = parsed["deltap_wrt_ref_values"]
                if not y_values:
                    continue
                x_values = list(range(1, len(y_values) + 1))
                color = color_cycle[i % len(color_cycle)]
                label = tab_ctx.name
                plot.plot(
                    x_values,
                    y_values,
                    pen=pg.mkPen(color=color, width=2),
                    symbol="o",
                    symbolSize=7,
                    symbolBrush=pg.mkBrush(color),
                    name=label,
                )
                results_path = str(tab_ctx.optimisation_results_file) if tab_ctx.optimisation_results_file else "N/A"
                table_rows.append(
                    (
                        label,
                        self._format_deltap_value(float(parsed["mean_wrt_ref"])),
                        self._format_deltap_value(float(parsed["stderr_wrt_ref"])),
                        results_path,
                    )
                )
            title_latex = f"Measured $\\Delta p$ w.r.t. {int(title_ref_energy)} GeV vs Arc"
            plot.setTitle(latex_to_html_converter(title_latex), color=colors.BLACK)

            info_table.setRowCount(len(table_rows))
            for row_idx, (tab_name, mean_txt, stderr_txt, path_txt) in enumerate(table_rows):
                info_table.setItem(row_idx, 0, QtWidgets.QTableWidgetItem(tab_name))
                info_table.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(mean_txt))
                info_table.setItem(row_idx, 2, QtWidgets.QTableWidgetItem(stderr_txt))
                info_table.setItem(row_idx, 3, QtWidgets.QTableWidgetItem(path_txt))

        selector.itemChanged.connect(lambda _: redraw_plot())
        redraw_plot()

        self._results_plot_dialog = dialog
        dialog.show()

    @staticmethod
    def _format_deltap_value(value: float) -> str:
        """Format delta-p values with 3 s.f. and exponent constrained to -4 or -5."""
        if value == 0:
            return "0"
        exponent = -4 if abs(value) >= 1e-4 else -5
        mantissa = value / (10 ** exponent)
        superscript_exponent = str(exponent).translate(DppOptimisationController._SUPERSCRIPT_DIGITS)
        return f"{mantissa:.3g} × 10{superscript_exponent}"

    @staticmethod
    def _format_deltap_latex(value: float) -> str:
        """Format delta-p values as LaTeX with 3 s.f. and exponent -4/-5 only."""
        if value == 0:
            return "0"
        exponent = -4 if abs(value) >= 1e-4 else -5
        mantissa = value / (10 ** exponent)
        return f"{mantissa:.3g}\\times10^{{{exponent}}}"

    def _read_deltap_results_for_plot(self) -> dict[str, float | list[float]]:
        """Read plotting values from results file, without recomputing available summary stats."""
        return self._read_deltap_results_for_context(
            OptimisationTabContext(
                name="current",
                optimisation_results_file=self._optimisation_results_file,
                latest_deltap_wrt_ref_results=self._latest_deltap_wrt_ref_results,
                latest_fitted_deltap_wrt_model_energy=self._latest_fitted_deltap_wrt_model_energy,
                latest_model_energy_gev=self._latest_model_energy_gev,
                latest_ref_energy=self._latest_ref_energy,
            )
        )

    def _read_deltap_results_for_context(
        self,
        context: OptimisationTabContext,
    ) -> dict[str, float | list[float]]:
        """Read plotting values from one tab context."""
        values: list[float] = []
        mean_wrt_ref: float | None = None
        stderr_wrt_ref: float | None = None
        model_energy_gev: float | None = None
        ref_energy: float | None = None
        deltap_col_idx: int | None = None

        results_file = context.optimisation_results_file
        if results_file is not None and results_file.exists():
            for raw_line in results_file.read_text().splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                if line.startswith("#"):
                    parts = line[1:].split("\t")
                    if len(parts) >= 2 and parts[0].strip() == "model_energy_reference_GeV":
                        try:
                            model_energy_gev = float(parts[1].strip())
                        except ValueError:
                            pass
                    if len(parts) >= 2 and parts[0].strip() == "output_energy_reference_GeV":
                        try:
                            ref_energy = float(parts[1].strip())
                        except ValueError:
                            pass
                    continue

                fields = line.split("\t")
                key = fields[0].strip()
                value = fields[1].strip() if len(fields) > 1 else ""
                lower_fields = [field.strip().lower() for field in fields]

                if key.lower() == "range":
                    deltap_col_name = f"deltap_wrt_{int(ref_energy)}gev" if ref_energy is not None else "deltap_wrt_6800gev"
                    if deltap_col_name in lower_fields:
                        deltap_col_idx = lower_fields.index(deltap_col_name)
                    elif "deltap" in lower_fields:
                        deltap_col_idx = lower_fields.index("deltap")
                    else:
                        deltap_col_idx = 1
                    continue

                if key.startswith("arc"):
                    if deltap_col_idx is None:
                        deltap_col_idx = 1
                    if deltap_col_idx >= len(fields):
                        continue
                    try:
                        values.append(float(fields[deltap_col_idx].strip()))
                    except ValueError:
                        continue
                    continue

                mean_key = f"MeanDeltaP_wrt_{int(ref_energy)}GeV" if ref_energy is not None else "MeanDeltaP_wrt_6800GeV"
                if key in (mean_key, "MeanArcs") and value:
                    try:
                        mean_wrt_ref = float(value)
                    except ValueError:
                        pass
                    continue

                stderr_key = f"StdErrDeltaP_wrt_{int(ref_energy)}GeV" if ref_energy is not None else "StdErrDeltaP_wrt_6800GeV"
                if key in (stderr_key, "StdErrArcs") and value:
                    try:
                        stderr_wrt_ref = float(value)
                    except ValueError:
                        pass
                    continue

        # Fallbacks only for missing values not available in the file.
        if not values:
            values = list(context.latest_deltap_wrt_ref_results)
        if mean_wrt_ref is None and values:
            mean_wrt_ref = float(pd.Series(values).mean())
        if stderr_wrt_ref is None and values:
            std = float(pd.Series(values).std(ddof=0))
            stderr_wrt_ref = std / (len(values) ** 0.5)
        if model_energy_gev is None:
            model_energy_gev = (
                context.latest_model_energy_gev
                if context.latest_model_energy_gev is not None
                else float("nan")
            )
        if ref_energy is None:
            ref_energy = 6800.0  # default

        return {
            "deltap_wrt_ref_values": values,
            "mean_wrt_ref": mean_wrt_ref if mean_wrt_ref is not None else float("nan"),
            "stderr_wrt_ref": stderr_wrt_ref if stderr_wrt_ref is not None else float("nan"),
            "model_energy_gev": model_energy_gev,
            "ref_energy": ref_energy,
        }

    @Slot(int)
    def _on_arc_selection_changed(self, index: int):
        """Handle arc selection change in dropdown."""
        self._update_arc_info()

    def _update_arc_info(self):
        """Update the arc information display."""
        index = self._view.get_selected_arc_index()
        if index >= 0:
            arc = self._arc_list_model.get_arc(index)
            if arc:
                # Extract start position from BPM name
                import re

                match = re.search(r"BPM\.(\d+)[RL]", arc.magnet_range_start_bpm)
                start_pos = int(match.group(1)) if match else 9

                # Calculate number of BPMs
                num_start_bpms = len(range(start_pos, arc.bpm_start_max_position + 1, arc.bpm_step))
                num_end_bpms = len(range(start_pos, arc.bpm_end_max_position + 1, arc.bpm_step))

                info = (
                    f"<b>{arc.name}</b><br>"
                    f"Magnet Range: {arc.magnet_range_start_bpm} → {arc.magnet_range_end_bpm}<br>"
                    f"S Position: {arc.magnet_range_start_s:.2f} m → {arc.magnet_range_end_s:.2f} m<br>"
                    f"BPM Step: {arc.bpm_step}, Start Max: {arc.bpm_start_max_position}, End Max: {arc.bpm_end_max_position}<br>"
                    f"Number of BPMs: {num_start_bpms} start, {num_end_bpms} end"
                )
                self._view.update_arc_info(info)
                return

        self._view.update_arc_info(DEFAULT_ARC_INFO_TEXT)

    def _update_measurement_buttons(self):
        """Update measurement-related button states."""
        has_selection = self._view.get_selected_measurement_index() >= 0
        has_analysis = self._analysis_dir is not None
        self._view.enable_measurement_removal(has_selection and has_analysis)

    def _update_action_buttons(self):
        """Update action button states based on current state."""
        has_model = self._model_info is not None and self._model_info.beam is not None
        has_analysis = self._analysis_dir is not None
        has_measurements = len(self._measurement_list_model.get_all_files()) > 0
        is_busy = self._get_running_processes_count() > 0
        has_results = (
            self._optimisation_results_file is not None and self._optimisation_results_file.exists()
        )

        if self._optimisation_running:
            self._view.set_optimisation_lockdown(True, allow_view_results=has_results)
            return

        self._view.set_optimisation_lockdown(False)

        self._view.enable_measurement_addition(has_model and has_analysis)

        # Download knobs enabled if we have model and measurements
        self._view.enable_download_knobs(has_model and has_analysis and has_measurements)

        # Parallel prepare button uses same prerequisites as download/datafile inputs.
        self._view.enable_prepare_inputs_parallel(has_model and has_analysis and has_measurements)

        # Create datafile enabled if we have model and measurements.
        self._view.enable_create_datafile(
            has_model and has_analysis and has_measurements
        )
        if self._prepare_inputs_running:
            self._view.enable_prepare_inputs_parallel(False)
            self._view.enable_download_knobs(False)
            self._view.enable_create_datafile(False)

        # Run optimisation enabled if datafile is created
        self._view.enable_run_optimisation(
            has_model and has_analysis and has_measurements and self._datafile_created and not is_busy
        )
        self._view.enable_save_results(has_results)
        self._view.enable_view_results(bool(self._latest_deltap_wrt_ref_results))
        has_model_source_tab = any(
            idx != self._active_tab_index and ctx.model_info is not None
            for idx, ctx in enumerate(self._optimisation_tabs)
        )
        self._view.enable_copy_model_from_tab(has_model_source_tab)

    def _validate_for_knob_download(self) -> bool:
        """Validate that we can download knobs."""
        if not self._model_info or self._model_info.beam is None:
            show_error_dialog(
                title="No Model Selected",
                message="Please select a model directory first.",
                parent=self._view,
            )
            return False

        if self._analysis_dir is None:
            show_error_dialog(
                title="No Analysis Selected",
                message="Please select an analysis directory first.",
                parent=self._view,
            )
            return False

        if len(self._measurement_list_model.get_all_files()) == 0:
            show_error_dialog(
                title="No Measurements",
                message="Please add measurement files first.",
                parent=self._view,
            )
            return False

        return True

    def _validate_for_datafile_creation(self) -> bool:
        """Validate that we can create datafile."""
        return self._validate_for_knob_download()

    def _validate_for_optimisation(self) -> bool:
        """Validate that we can run optimisation."""
        if not self._validate_for_datafile_creation():
            return False

        if len(self._arc_list_model.get_all_arcs()) == 0:
            show_error_dialog(
                title="No Arcs Configured",
                message="Please configure arcs first.",
                parent=self._view,
            )
            return False

        return True

    def _extract_measurement_datetimes_from_files(self) -> list[pd.Timestamp]:
        """Extract UTC datetimes from measurement filenames."""
        datetimes: list[pd.Timestamp] = []
        files = self._measurement_list_model.get_all_files()

        for file_path in files:
            filename = file_path.name

            # Preferred pattern: YYYY_MM_DD_HH_MM_SS_mmm
            full_match = re.search(
                r"(\d{4})[_-](\d{2})[_-](\d{2})[_-](\d{2})[_-](\d{2})[_-](\d{2})[_-](\d{3})",
                filename,
            )
            if full_match:
                year, month, day, hour, minute, second, millis = (
                    int(group) for group in full_match.groups()
                )
                datetimes.append(
                    pd.Timestamp(
                        year=year,
                        month=month,
                        day=day,
                        hour=hour,
                        minute=minute,
                        second=second,
                        microsecond=millis * 1000,
                        tz="UTC",
                    )
                )
                continue

            # Fallback pattern: HH_MM_SS_mmm; use file modification date in UTC.
            time_match = re.search(r"(\d{2})_(\d{2})_(\d{2})_(\d{3})", filename)
            if time_match:
                hour, minute, second, millis = (int(group) for group in time_match.groups())
                file_date = pd.Timestamp(file_path.stat().st_mtime, unit="s", tz="UTC")
                datetimes.append(
                    pd.Timestamp(
                        year=file_date.year,
                        month=file_date.month,
                        day=file_date.day,
                        hour=hour,
                        minute=minute,
                        second=second,
                        microsecond=millis * 1000,
                        tz="UTC",
                    )
                )

        return datetimes

    def _check_required_files_exist(self) -> bool:
        """Check if all required files exist."""
        return optimisation_service.check_required_files_exist(self)
