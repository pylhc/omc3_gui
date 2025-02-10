""" 
Segment-by-Segment Controller
-----------------------------

This is the main controller for the Segment-by-Segment application.
"""
from __future__ import annotations

import logging
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from omc3.sbs_propagation import segment_by_segment
from qtpy import QtWidgets
from qtpy.QtCore import Slot

from omc3_gui.segment_by_segment.defaults import DEFAULT_SEGMENTS
from omc3_gui.segment_by_segment.main_model import SegmentTableModel, Settings
from omc3_gui.segment_by_segment.main_view import SbSWindow
from omc3_gui.segment_by_segment.measurement_model import OpticsMeasurement
from omc3_gui.segment_by_segment.measurement_view import OpticsMeasurementDialog
from omc3_gui.segment_by_segment.segment_model import (
    SegmentDataModel,
    SegmentItemModel,
    compare_segments,
)
from omc3_gui.segment_by_segment.segment_view import SegmentDialog
from omc3_gui.utils.file_dialogs import OpenDirectoriesDialog
from omc3_gui.utils.threads import BackgroundThread
from omc3_gui.utils.ui_base_classes import Controller

if TYPE_CHECKING:
    from collections.abc import Sequence

LOGGER = logging.getLogger(__name__)

class SbSController(Controller):
    
    settings: Settings
    _view: SbSWindow

    def __init__(self):
        super().__init__(SbSWindow())
        self.connect_signals()
        self.settings = Settings()
        self._last_selected_optics_path: Path | None = None
        self._running_tasks: list[BackgroundThread] = []

        self.set_measurement_interaction_buttons_enabled(False)
        self.set_all_segment_buttons_enabled(False)

    def connect_signals(self):
        """ Connect the signals from the GUI components (view) to the slots (controller). """
        view: SbSWindow = self._view  # for shorthand and type hinting

        # Measurements -------------------------------------------------------------
        view.button_load_measurement.clicked.connect(self.open_measurements)
        view.button_edit_measurement.clicked.connect(self.edit_measurement)
        view.button_remove_measurement.clicked.connect(self.remove_measurement)

        view.button_run_matcher.clicked.connect(self.run_matcher)
        view.button_edit_corrections.clicked.connect(self.edit_corrections)

        view.sig_list_measurements_double_clicked.connect(self.edit_measurement)
        view.sig_list_measurements_selected.connect(self.measurement_selection_changed)

        # Segments -------------------------------------------------------------
        view.button_new_segment.clicked.connect(self.new_segment)
        view.button_copy_segment.clicked.connect(self.copy_segment)
        view.button_default_segments.clicked.connect(self.add_default_segments)
        view.button_remove_segment.clicked.connect(self.remove_segment)
        view.button_run_segment.clicked.connect(self.run_segments)
        view.button_save_segments.clicked.connect(self.save_segments)
        view.button_load_segments.clicked.connect(self.load_segments)

        view.sig_table_segments_selected.connect(self.segment_selection_changed)
        view.sig_thread_spinner_double_clicked.connect(self._show_running_tasks)
    
    @Slot()
    def _update_tasks_status(self):
        """ Update the status bar with the number of running tasks. """
        view: SbSWindow = self._view  
        status_bar: QtWidgets.QStatusBar = view.statusBar()  # seems to return it, if already exist, because spinner is there
        
        if self._running_tasks:
            # status_bar.show()  # looks nice, but moves the window around too much ... 
            status_bar.showMessage(f"{len(self._running_tasks)} Task(s) running ...")
            status_bar.setToolTip(
                f"{len(self._running_tasks)} Running Task(s):\n  - "
                + "\n  - ".join([task.message for task in self._running_tasks])
            )
            view.thread_spinner.start()
        else:
            status_bar.setToolTip(None)
            status_bar.clearMessage()
            view.thread_spinner.stop()
            # status_bar.hide()

    @Slot()
    def _add_running_task(self, task: BackgroundThread):
        """ Add a task to the list of running tasks. """
        
        # Automatically remove task when finished
        remove_task_fun = partial(self._remove_running_task, task=task)
        task.finished.connect(remove_task_fun)

        self._running_tasks.append(task)
        self._update_tasks_status()

    @Slot()
    def _remove_running_task(self, task):
        """ Remove a task from the list of running tasks. """
        self._running_tasks.remove(task)
        self._update_tasks_status()

    @Slot()
    def _show_running_tasks(self):
        """ Show (i.e. log) the list of running tasks. """
        LOGGER.debug(f"Running tasks: {[task.message for task in self._running_tasks]}")
    
    # Measurements -------------------------------------------------------------
    def set_measurement_interaction_buttons_enabled(self, enabled: bool = True):
        """ Enable/disable the buttons that interact with measurements. 
        
        Args:
            enabled (bool): True to enable, False to disable.
        """
        view: SbSWindow = self._view  

        measurement_interaction_buttons = (
            view.button_remove_measurement,
            view.button_edit_measurement,
            view.button_run_matcher,
            view.button_edit_corrections,
        )
        for button in measurement_interaction_buttons:
            button.setEnabled(enabled)


    def add_measurement(self, measurement: OpticsMeasurement):
        """ Add a measurement to the GUI. 
        
        Args:
            measurement (OpticsMeasurement): The measurement to add.
        """
        view: SbSWindow = self._view  # for type hinting
        view.get_measurement_list().add_item(measurement) 
    
    @Slot()
    def open_measurements(self):
        """ Open the file dialog for optics measurements. """
        view: SbSWindow = self._view  

        LOGGER.debug("Opening new optics measurement. Asking for folder paths.")
        filenames = OpenDirectoriesDialog(
            parent=view,
            caption="Select Optics Folders", 
            directory=str(self._last_selected_optics_path) if self._last_selected_optics_path else None,
        ).run_selection_dialog()

        loaded_measurements = view.get_measurement_list()
        measurement_indices = []

        LOGGER.debug(f"User selected {len(filenames)} files.")
        for filename in filenames:
            LOGGER.debug(f"adding: {filename!s}")
            optics_measurement = OpticsMeasurement.from_path(filename)
            try:
                loaded_measurements.add_item(optics_measurement)
            except ValueError as e:
                LOGGER.error(str(e))
            else:
                measurement_indices.append(loaded_measurements.get_index(optics_measurement))

            self._last_selected_optics_path = filename.parent

        view.set_selected_measurements(measurement_indices)
    
    @Slot()
    def edit_measurement(self, measurement: OpticsMeasurement | None = None):
        """ Open the edit dialog for a measurement.
        If no measurement is given, the currently selected measurement is used.

        Args:
            measurement (OpticsMeasurement | None, optional): The measurement to edit. Defaults to None.
        """
        if measurement is None:
            try:
                measurement = self.get_single_measurement()
            except ValueError as e:
                LOGGER.warning(str(e))
                return

        LOGGER.debug(f"Opening edit dialog for {measurement.display()}.")
        dialog = OpticsMeasurementDialog(
            parent=self._view,
            optics_measurement=measurement,
        )
        if dialog.exec_() == dialog.Accepted:
            LOGGER.debug("Edit dialog closed. Updating measurement.")

    @Slot()
    def remove_measurement(self, measurements: Sequence[OpticsMeasurement] | None = None):
        """ Remove measurements from the GUI.
        If no measurements are given, the currently selected measurements are removed.        

        Args:
            measurements (Sequence[OpticsMeasurement] | None, optional): The measurements to remove. Defaults to None.
        """
        view: SbSWindow = self._view  

        if measurements is None:
            measurements = view.get_selected_measurements()
            if not len(measurements):
                LOGGER.warning("No measurement selected.")
                return
        
        view.get_measurement_list().remove_items(measurements)
        view.set_selected_measurements()

    @Slot(tuple)
    def measurement_selection_changed(self, measurements: Sequence[OpticsMeasurement]):
        """ Updates the GUI when the selected measurements change. 
        
        Args:
            measurements: Sequence[OpticsMeasurement]: The new selection of measurements.
        """
        LOGGER.debug(f"Selected {len(measurements)} measurements.")
        view: SbSWindow = self._view  

        if not len(measurements):
            self.set_measurement_interaction_buttons_enabled(False)
            view.set_segments(SegmentTableModel())
            self.segment_selection_changed()
            self.set_all_segment_buttons_enabled(False)
            return

        self.set_measurement_interaction_buttons_enabled(True)
        self.set_all_segment_buttons_enabled(True)

        segment_table_items: list[SegmentItemModel] = []

        for measurement in measurements:
            for segment in measurement.segments:
                for segment_item in segment_table_items:
                    if compare_segments(segment, segment_item):
                        segment_item.append_segment(segment)
                        break
                else:
                    segment_table_items.append(SegmentItemModel.from_segments([segment]))

        segment_table = SegmentTableModel()
        segment_table.add_items(segment_table_items)
        view.set_segments(segment_table)
        self.segment_selection_changed()

    def get_single_measurement(self) -> OpticsMeasurement:
        """ Get a single selected measurement from the GUI. 
        Raises ValueError if no measurement is selected or multiple measurements are selected. 
        """
        view: SbSWindow = self._view  
        measurements = view.get_selected_measurements()

        if len(measurements) == 0:
            raise ValueError("Please select at least one measurement.")

        if len(measurements) > 1:
            raise ValueError("Please select only one measurement.")
        
        return measurements[0]

    @ Slot()
    def run_matcher(self) -> None:
        """ Run the matcher. """
        view: SbSWindow = self._view

        # TODO:
        msg = "The Segment-by-Segment Matcher is not implemented yet."
        LOGGER.error(msg)
        view.showErrorDialog("Error: Not Implemented", msg)
    
    @ Slot()
    def edit_corrections(self) -> None:
        """ Edit the corrections file. """
        view: SbSWindow = self._view

        # TODO:
        msg = "Not implemented yet."
        LOGGER.error(msg)
        view.showErrorDialog("Error: Not Implemented", msg)

    
    # Segments -----------------------------------------------------------------

    def set_segment_interaction_buttons_enabled(self, enabled: bool = True):
        """ Enable/disable the buttons that interact with segments. 
    
        Args:    
            enabled (bool): True to enable, False to disable.
        """
        view: SbSWindow = self._view  

        segment_interaction_buttons = (
            view.button_run_segment,
            view.button_copy_segment,
            view.button_remove_segment,
        )
        for button in segment_interaction_buttons:
            button.setEnabled(enabled)
    
    def set_all_segment_buttons_enabled(self, enabled: bool = True):
        """ Enable/disable all segment buttons. 
    
        Args:
            enabled (bool): True to enable, False to disable.
        """
        view: SbSWindow = self._view  

        segment_buttons = (
            view.button_run_segment,
            view.button_copy_segment,
            view.button_remove_segment,
            view.button_new_segment,
            view.button_default_segments,
            view.button_save_segments,
            view.button_load_segments,
        )
        for button in segment_buttons:
            button.setEnabled(enabled)

    @Slot(tuple)
    def segment_selection_changed(self, segments: Sequence[SegmentItemModel] | None = None):
        """ Updates the GUI when the selected segments change.
        If no segments are given, the currently selected segments are used.
        
        Args:
            segments: Sequence[SegmentItemModel]: The new selection of segments.
        """
        view: SbSWindow = self._view  
        view.clear_plots()

        if segments is None:
            segments = view.get_selected_segments()
            
        LOGGER.debug(f"{len(segments)} Segment(s) selected.")
        if not len(segments):
            self.set_segment_interaction_buttons_enabled(False)
            return

        self.set_segment_interaction_buttons_enabled(True)
        if len(segments) > 1:
            LOGGER.debug("More than one segment selected. Clearing Plots.")
            return

        view.plot()

    @Slot()
    def add_default_segments(self):
        """ Add default segments to the currently selected measurements. 
        These segments are defined in :data:`omc3_gui.segment_by_segment.defaults.DEFAULT_SEGMENTS`. 
        """
        LOGGER.debug("Adding default segments.")
        view: SbSWindow = self._view  

        selected_measurements = view.get_selected_measurements()
        if not selected_measurements:
            LOGGER.error("Please select at least one measurement.")
            return

        for measurement in selected_measurements:
            beam = measurement.beam
            if beam is None:
                LOGGER.error(f"No beam found in measurement {measurement.display()}. Cannot add default segments.")
                continue

            for segment_tuple in DEFAULT_SEGMENTS:
                segment = SegmentDataModel(measurement, *segment_tuple)
                segment.start = f"{segment.start}.B{beam}"
                segment.end = f"{segment.end}.B{beam}"
                measurement.try_add_segment(segment)

        self.measurement_selection_changed(selected_measurements)

    @Slot()
    def new_segment(self):
        """ Create a new segment and add it to the currently selected measurements. """
        LOGGER.debug("Creating new segment.")
        view: SbSWindow = self._view  

        selected_measurements = view.get_selected_measurements()
        if not selected_measurements:
            LOGGER.error("Please select at least one measurement.")
            return
        
        LOGGER.debug("Opening edit dialog for a new segment.")
        dialog = SegmentDialog(parent=view)
        if dialog.exec_() == dialog.Rejected:
            LOGGER.debug("Segment dialog cancelled.")
            return
        
        LOGGER.debug("Segment dialog closed. Updating segement.")
        for measurement in selected_measurements:
            new_segment_copy = dialog.segment.copy()
            new_segment_copy.measurement = measurement
            measurement.try_add_segment(new_segment_copy)

        self.measurement_selection_changed(selected_measurements)
    
    @Slot()
    def copy_segment(self, segments: Sequence[SegmentItemModel] | None = None):
        """ Create a copy of the given segments and add them to the currently selected measurements. 
        If no segments are given, the currently selected segments are copied.

        Args:
            segments: Sequence[SegmentItemModel]: The segments to copy.
        """
        view: SbSWindow = self._view  

        if segments is None:
            segments = view.get_selected_segments()
        
        if not segments:
            LOGGER.error("Please select at least one segment to copy.")
            return

        LOGGER.debug(f"Copying {len(segments)} segments.")
        selected_measurements = view.get_selected_measurements()
        if not selected_measurements:
            LOGGER.error("Please select at least one measurement.")
            return

        for segment_item in segments:
            new_segment_name = f"{segment_item.name} - Copy"
            for measurement in selected_measurements:  
                # Check if copied segment name already exists in one of the measurements
                try:
                    measurement.get_segment_by_name(new_segment_name)
                except NameError:
                    pass
                else:
                    LOGGER.error(
                        f"Could not create copy \"{new_segment_name}\" as it already exists in {measurement.display()}."
                    )
                    break
            else:
                # None of the measurements have the copied segment name, so add to the measurements
                for measurement in selected_measurements:
                    for segment in segment_item.segments:
                        new_segment = segment.copy()
                        new_segment.name = new_segment_name
                        measurement.try_add_segment(new_segment)
            
        self.measurement_selection_changed(selected_measurements)
    
    @Slot()
    def remove_segment(self, segments: Sequence[SegmentItemModel] | None = None):
        """ Remove the given segments from the currently selected measurements. 
        If no segments are given, the currently selected segments are removed.
        
        Args:
            segments: Sequence[SegmentItemModel]: The segments to remove.
        """
        view: SbSWindow = self._view  

        if segments is None:
            segments = view.get_selected_segments()
        
        if not segments:
            LOGGER.error("Please select at least one segment to remove.")
            return

        LOGGER.debug(f"Removing {len(segments)} segments.")
        selected_measurements = view.get_selected_measurements()
        if not selected_measurements:
            LOGGER.error("Please select at least one measurement.")
            return

        for measurement in selected_measurements:
            for segment_item in segments:
                measurement.try_remove_segment(segment_item.name)

        self.measurement_selection_changed(selected_measurements)

    @Slot()
    def load_segments(self):
        LOGGER.debug("Loading segments from file/folder.")
        # TODO
        # Either parse a folder to find the segements therein, or load from a json file.
        
    @Slot()
    def save_segments(self):
        LOGGER.debug("Saving segments to a file.")
        # TODO
        # Save current segements to a json file

    @Slot()
    def run_segments(self, segments: Sequence[SegmentItemModel] | None = None):
        """ Run the given segments on the currently selected measurements.
        If no segments are given, the currently selected segments are run.
        
        Args:
            segments: Sequence[SegmentItemModel]: The segments to run.
        """
        view: SbSWindow = self._view  

        if segments is None:
            segments = view.get_selected_segments()
        
        if not segments:
            LOGGER.error("Please select at least one segment to run.")
            return

        LOGGER.debug(f"Running {len(segments)} segments.")
        selected_measurements: Sequence[OpticsMeasurement] = view.get_selected_measurements()
        if not selected_measurements:
            LOGGER.error("Please select at least one measurement.")
            return

        segment_parameters = [s.to_input_string() for s in segments if not s.is_element()]
        element_parameters = [s.to_input_string() for s in segments if s.is_element()] 

        for measurement in selected_measurements:
            # Create sbs-callable from measurement/inputs
            sbs_function  = partial(
                    segment_by_segment, 
                    **measurement.get_sbs_parameters(),
                    segments=segment_parameters or None,
                    elements=element_parameters or None,
                )

            # Create thread
            measurement_task = BackgroundThread(
                function=sbs_function,
                message=f"SbS for {measurement.display()}",
            )
            
            # Run task
            LOGGER.info(f"Starting {measurement_task.message}")
            self._add_running_task(task=measurement_task)
            measurement_task.start()
            
            # For Debugging: Start sbs directly ---
            # sbs_function()
            # -------------------------------------
