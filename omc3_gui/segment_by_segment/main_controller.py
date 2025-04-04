""" 
Main Controller
---------------

This is the main controller for the Segment-by-Segment application.
"""
from __future__ import annotations

import logging
import re
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from omc3.sbs_propagation import segment_by_segment
from qtpy import QtWidgets
from qtpy.QtCore import Slot

from omc3_gui.plotting.classes import DualPlotWidget
from omc3_gui.segment_by_segment.defaults import (
    DEFAULT_SEGMENTS,
    get_default_correctors,
)
from omc3_gui.segment_by_segment.main_model import SegmentTableModel
from omc3_gui.segment_by_segment.main_view import SbSWindow
from omc3_gui.segment_by_segment.measurement_model import OpticsMeasurement
from omc3_gui.segment_by_segment.measurement_view import OpticsMeasurementDialog
from omc3_gui.segment_by_segment.plotting import plot_segment_data
from omc3_gui.segment_by_segment.segment_model import (
    SegmentDataModel,
    SegmentItemModel,
    compare_segments,
    get_segments_from_directory,
)
from omc3_gui.segment_by_segment.segment_view import SegmentDialog
from omc3_gui.segment_by_segment.settings import PlotSettings, Settings
from omc3_gui.ui_components.base_classes_cvm import Controller
from omc3_gui.ui_components.dataclass_ui import SettingsDialog
from omc3_gui.ui_components.file_dialogs import OpenAnyMultiDialog, OpenAnySingleDialog
from omc3_gui.ui_components.message_boxes import show_confirmation_dialog
from omc3_gui.ui_components.text_editor import TextEditorDialog
from omc3_gui.ui_components.threads import BackgroundThread

if TYPE_CHECKING:
    from collections.abc import Sequence

LOGGER = logging.getLogger(__name__)

class SbSController(Controller):
    
    settings: Settings
    _view: SbSWindow

    def __init__(self, measurements: list[Path | str] | None = None, settings: Settings | None = None):
        super().__init__(SbSWindow())
        self.settings: Settings = settings or Settings()
        self._last_selected_measurement_path: Path = self.settings.main.cwd
        self._running_tasks: list[BackgroundThread] = []

        self.connect_signals()
        self.set_measurement_interaction_buttons_enabled(False)
        self.set_all_segment_buttons_enabled(False)
        
        if measurements is not None:
            self.open_measurements_from_paths(measurements)        

    def connect_signals(self):
        """ Connect the signals from the GUI components (view) to the slots (controller). """
        view: SbSWindow = self._view  # for shorthand and type hinting

        # Tabs -----------------------------------------------------------------
        view.sig_tab_changed.connect(self.plot)

        # Menu Bar -------------------------------------------------------------
        view.sig_menu_settings.connect(self.show_settings)

        view.add_settings_to_menu(
            menu="View",
            settings=self.settings.plotting,
            hook=self.plot,
        )

        view.sig_menu_clear_all.connect(self.clear_all_data)

        # Measurements -------------------------------------------------------------
        view.button_load_measurement.clicked.connect(self.open_measurements)
        view.button_edit_measurement.clicked.connect(self.edit_measurement)
        view.button_remove_measurement.clicked.connect(self.remove_measurement)
        view.button_copy_measurement.clicked.connect(self.copy_measurement)

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

    # Tasks --------------------------------------------------------------------  
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
    def _remove_running_task(self, task: BackgroundThread):
        """ Remove a task from the list of running tasks. """
        self._running_tasks.remove(task)
        self._update_tasks_status()
        if not self._running_tasks:
            self.clear_all_data() # last task finished, update plots

    @Slot()
    def _show_running_tasks(self):
        """ Show (i.e. log) the list of running tasks. """
        LOGGER.info(f"Running tasks: {[task.message for task in self._running_tasks]}")
        
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
            view.button_copy_measurement,
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

        LOGGER.debug("Opening new optics measurement. Asking for paths.")
        filenames = OpenAnyMultiDialog(
            parent=view,
            caption="Select Optics Folders/SbS Folders/SbS json", 
            directory=self._last_selected_measurement_path,
        ).run_selection_dialog()

        self.open_measurements_from_paths(filenames, select=True)

    def open_measurements_from_paths(self, paths: Sequence[Path | str], select: bool = False):
        """ Open the given paths as measurements. """
        if not len(paths):
            LOGGER.debug("No measurement paths to load.")
            return

        view: SbSWindow = self._view
        loaded_measurements = view.get_measurement_list()
        measurement_indices = []

        for filename in paths:
            LOGGER.debug(f"Adding: {filename!s}")
            if filename.is_dir():
                optics_measurement = OpticsMeasurement.from_path(filename)
            elif filename.is_file() and filename.suffix == ".json":
                optics_measurement = OpticsMeasurement.from_json(filename)
            else:
                LOGGER.error(f"Invalid file: {filename}")
                continue

            try:
                optics_measurement.quick_check()
            except ValueError as e:
                LOGGER.warning(str(e))  # Maybe even popup?
            except NameError as e:
                LOGGER.error(f"{e!s} ({filename})")
                continue

            if self.settings.main.autoload_segments:
                self.load_segments_for_measurement(optics_measurement)

            if self.settings.main.autodefault_segments:
                self.add_default_segments(optics_measurement)

            try:
                loaded_measurements.add_item(optics_measurement)
            except ValueError as e:
                LOGGER.error(str(e))
            else:
                if select: 
                    measurement_indices.append(loaded_measurements.get_index(optics_measurement))

            self._last_selected_measurement_path = filename.parent

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
        view: SbSWindow = self._view  
        dialog = OpticsMeasurementDialog(
            parent=view,
            optics_measurement=measurement,
        )
        if dialog.exec_() == dialog.Accepted:
            LOGGER.debug("Edit dialog closed. Updating measurement.")

        try:
            measurement.quick_check()
        except ValueError as e:
            LOGGER.warning(str(e))  # Maybe even popup?
        except NameError as e:
            LOGGER.error(str(e))
            return
        
        try:
            measurement.to_json()
        except IOError as e:
            LOGGER.warning(str(e))


    @Slot()
    def copy_measurement(self, measurement: OpticsMeasurement | None = None):
        """ Create a copy of the given measurement and add it to the GUI. 
        If no measurement is given, the currently selected measurement is copied.

        Args:
            measurement (OpticsMeasurement | None, optional): The measurement to copy. Defaults to None.
        """
        if measurement is None:
            try:
                measurement = self.get_single_measurement()
            except ValueError as e:
                LOGGER.warning(str(e))
                return

        if measurement.output_dir is None:  # should not be possible, but better to catch
            LOGGER.error("Cannot copy measurement without output directory.")
            return

        LOGGER.debug(f"Copying {measurement.display()}.")
        new_measurement = measurement.copy()
        
        # might already have a counter from previous copy
        name =  re.sub(r"_\d+$", "", measurement.output_dir.name)  

        for count in range(1, 1000):  # limit to avoid infinite loop
            new_measurement.output_dir = measurement.output_dir.with_name(f"{name}_{count:d}")
            try:
                self.add_measurement(new_measurement)
            except ValueError:
                continue
            break
        else:
            LOGGER.error(
                "Could not copy measurement. Counter limit exeeded. Not sure what went wrong."
            )
            return

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
            view.set_segments_table(SegmentTableModel())
            self.segment_selection_changed()
            self.set_all_segment_buttons_enabled(False)
            return

        self.set_measurement_interaction_buttons_enabled(True)
        if len(measurements) > 1:
            view.button_edit_measurement.setEnabled(False)
            view.button_copy_measurement.setEnabled(False)

        self.set_all_segment_buttons_enabled(True)

        # Group the segments for the measurements into table-items when they have the same defintion ---
        segment_table_items: list[SegmentItemModel] = []

        for measurement in measurements:
            for segment in measurement.segments:
                for segment_item in segment_table_items:
                    if compare_segments(segment, segment_item):
                        segment_item.append_segment(segment)
                        break
                else:
                    segment_table_items.append(SegmentItemModel.from_segments([segment]))

        # Create the segment Table to show in the GUI ---
        segment_table = SegmentTableModel()
        try:
            segment_table.add_items(segment_table_items)
        except ValueError as e:
            LOGGER.debug(str(e))
            
        view.set_segments_table(segment_table)
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
        view.showErrorDialog("Error: Not Implemented", "The Segment-by-Segment Matcher is not implemented yet.")
        # TODO!
    
    @ Slot()
    def edit_corrections(self) -> None:
        """ Edit the corrections file. 
        
        The following logic is applied to the selected measurements:
        
        - Check if a measurement is selected:
        - If not show error.

        - Check if multiple measurements are selected, if so: 
            a) they all have the same correction file: open TextEditor, 
            c) they have different correction files: show error
            b) some have the same correction file, all others have none: ask if the others should also get this one
            d) they have no correction file: ask for path and then open TextEditor with that file
        - If only a single measurement is s
        """
        view: SbSWindow = self._view

        selected_measurements: tuple[OpticsMeasurement] = view.get_selected_measurements()
        if not selected_measurements:
            LOGGER.error("Please select at least one measurement.")
            return
        
        correction_files = {measurement.corrections for measurement in selected_measurements if measurement.corrections}
        if len(correction_files) > 1:
            view.showErrorDialog(
                title="Error: Multiple correction files", 
                message="Please select only measurements using the same correction file."
            )
            return
        
        # Only one or none correction file within the selection measurements from here ---
        if len(correction_files) == 0:  # If there is none, ask user to provide one
            LOGGER.debug("No correction file selected. Asking.")
            directory = self.settings.main.cwd
            if len(selected_measurements) == 1:
                directory = selected_measurements[0].measurement_dir

            dialog = OpenAnySingleDialog(
                caption="Select a new or existing correction file for the selected measurement(s).",
                existing=False,  # can be a new file
                parent=view,
                directory=directory
            )
            correction_file = dialog.run_selection_dialog()
            if correction_file is None:
                LOGGER.error("No correction file to edit selected.")
                return

        else:  # There is only one. Maybe use it for all selected measurements
            correction_file = correction_files.pop()

            has_no_corrections = [m for m in selected_measurements if not m.corrections]
            if has_no_corrections:
                measurements_string = '\n'.join([m.display() for m in has_no_corrections])
                use_for_all = show_confirmation_dialog(
                    question=(
                        f"The measurements\n\n{measurements_string}\n\n"
                        "have no correction file assigned.\n"
                        f"Do you want to use\n\n{correction_file}\n\n"
                        "also for these measurements?"
                    ),
                    title="There are unset correction files",
                )
                if not use_for_all:
                    LOGGER.error(
                        "User does not want to use the same correction file for all selected measurements."
                        "Select a correction file for each measurement manually."
                    )
                    return
                
        # Use the correction file for all selected measurements ---
        # We could simply assign the correction file to all (as the other have the same file),
        # but this way we can log the changes (if even any).
        for measurement in selected_measurements:
            if not measurement.corrections:
                LOGGER.debug(f"Setting {correction_file} for {measurement.display()}")
                measurement.corrections = correction_file

        # Open the TextEditor for the selected correction file ---
        LOGGER.debug(f"Opening TextEditor for correction file: {correction_file}.")
        edit_dialog = TextEditorDialog(correction_file)

        if not correction_file.exists() and self.settings.main.suggest_correctors:
            text = get_default_correctors(selected_measurements[0])  # bit hacky but ok for now?
            edit_dialog.text_edit.setPlainText(text)

        edit_dialog.exec_()

    
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
        self.clear_plots()

        if segments is None:
            segments = view.get_selected_segments()
            
        LOGGER.debug(f"{len(segments)} Segment(s) selected.")
        if not len(segments):
            self.set_segment_interaction_buttons_enabled(False)
            return

        self.set_segment_interaction_buttons_enabled(True)
        self.plot()

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
            self.add_default_segements_to_measurement(measurement)

        self.measurement_selection_changed(selected_measurements)
    
    def add_default_segements_to_measurement(self, measurement: OpticsMeasurement): 
        """ Add default segments to the given measurement. 
        These segments are defined in :data:`omc3_gui.segment_by_segment.defaults.DEFAULT_SEGMENTS`. 

        Args:
            measurement (OpticsMeasurement): The measurement to add segments to.
        """
        if measurement.beam is not None:  # LHC
            for segment_tuple in DEFAULT_SEGMENTS:
                segment = SegmentDataModel(measurement, *segment_tuple)
                segment.start = f"{segment.start}.B{measurement.beam}"
                segment.end = f"{segment.end}.B{measurement.beam}"
                measurement.try_add_segment(segment, silent=True)
            return
        
        # TODO: Implement for other accelerators
        LOGGER.error(f"No beam found in measurement {measurement.display()}. Cannot add default segments.")


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
        dialog.validate_only_modified = False
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
            new_segment_name = f"{segment_item.name}_copy"
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
                        new_segment.measurement = measurement
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

        for segment_item in segments:
            for segment_data in segment_item.segments:
                segment_data.measurement.remove_segment(segment_data)
        
        self.measurement_selection_changed(view.get_selected_measurements())

    @Slot()
    def load_segments(self):
        self.load_segments_for_selected_measurements()
        # LOGGER.debug("Loading segments from file/folder.")
        # TODO: implement file saving and loading and ask user which one to do.
    
    def load_segments_for_selected_measurements(self):
        """ Load segments for the currently selected measurements. """
        LOGGER.debug("Loading segments for selected measurements.")
        view: SbSWindow = self._view

        selected_measurements = view.get_selected_measurements()
        if not selected_measurements:
            LOGGER.error("Please select at least one measurement.")
            return

        for measurement in selected_measurements:
            self.load_segments_for_measurement(measurement)

        # Update the view
        self.measurement_selection_changed(selected_measurements)

    def load_segments_for_measurement(self, measurement: OpticsMeasurement):
        """ Load segments for the given measurement. """
        LOGGER.debug(f"Loading segments for {measurement.display()}.")
        
        segments = get_segments_from_directory(measurement.output_dir)
        if not segments:
            LOGGER.debug(f"No segments found in {measurement.output_dir}.")
            return

        for segment_tuple in segments:
            segment = SegmentDataModel(measurement, *segment_tuple)
            measurement.try_add_segment(segment)
        
    @Slot()
    def save_segments(self):
        LOGGER.debug("Saving segments to a file.")
        view: SbSWindow = self._view
        view.showErrorDialog("Error: Not Implemented", "The save segments function is not implemented yet.")
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
            segments: Sequence[SegmentItemModel] = view.get_selected_segments()
        
        if not segments:
            LOGGER.error("Please select at least one segment to run.")
            return

        LOGGER.debug(f"Running {len(segments)} segments.")
        selected_measurements: Sequence[OpticsMeasurement] = view.get_selected_measurements()
        if not selected_measurements:
            LOGGER.error("Please select at least one measurement.")
            return
        
        all_selected_segment_data: list[SegmentDataModel] = [sdata for s in segments for sdata in s.segments]
        measurements_to_run: list[OpticsMeasurement] = [
            meas for meas in selected_measurements if any(s in meas.segments for s in all_selected_segment_data)
        ]

        for idx, measurement in enumerate(measurements_to_run):
            # Filter segments that are in the measurement and sort into segments/elements
            selected_segments_in_meas = [s for s in  all_selected_segment_data if s in measurement.segments]
            segment_parameters = [s.to_input_string() for s in selected_segments_in_meas if not s.is_element()]
            element_parameters = [s.to_input_string() for s in selected_segments_in_meas if s.is_element()] 

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
            
            # For Real Use: Run Task ---
            LOGGER.info(f"Starting {measurement_task.message}")
            self._add_running_task(task=measurement_task)
            measurement_task.start()
            # -------------------------------------

            # For Debugging: Start sbs directly ---
            # sbs_function()
            # self.clear_all_data()
            # LOGGER.info(f"Finished {measurement_task.message}")
            # -------------------------------------
    
    @Slot()
    def clear_all_data(self):
        """ Clear all segment data on all measurements. """
        view: SbSWindow = self._view
        measurements = view.get_all_measurements()
        for meas in measurements:
            clear_segments(meas.segments)
        self.plot()  # update plots -> reads needed data new

# Plotting ---------------------------------------------------------------------
    def plot(self, fail_ok: bool = True):
        """ Trigger a plot update with the currently selected segments. 
        
        This function is called when the user changes the selected segments or the settings.
        As a segment selection change is often triggered, i.e. when the user clicks on a segment in the table,
        e.g. to actually run this segment, one should not consider that the plot NEEDS to be updated.
        Hence in the default settings with ``fail_ok=True``, this function will mostly log to debug.

        This function is also called after the plotting settings are changed 
        (either in the settings dialog or in the menu), hence this is also a good place to warn the user
        if he did some mistakes there.
        """
        log_function = LOGGER.debug if fail_ok else LOGGER.error

        view: SbSWindow = self._view
        settings: PlotSettings = self.settings.plotting
        definition, widget = view.get_current_tab()
        
        self.clear_plots()

        if not settings.forward and not settings.backward:
            LOGGER.error("Please enable at least one propagation method to show.")
            return

        widget.set_connect_x(settings.connect_x)
        widget.set_connect_y(settings.connect_y)

        segments = view.get_selected_segments()
        if not len(segments):
            log_function("Not plotting, no segments selected.")
            return

        segments_data: list[SegmentDataModel] = [s_data for s in segments for s_data in s.segments if s_data.has_run()]
        if not len(segments_data):
            log_function("Not plotting, no segments have been run.")
            return

        if settings.same_start and not settings.model_s:  # only an issue if they all start at 0
            starts = {re.sub(r"\.B[12]$", "", s.start, flags=re.IGNORECASE) for s in segments_data}
            if len(starts) > 1:
                log_function("Not plotting, segments have different start BPMs (see 'Same Start' in settings).")
                return
        
        plot_segment_data(
            widget=widget, 
            definitions=definition, 
            segments=segments_data, 
            settings=settings,
        )

    def clear_plots(self):
        """ Clear the plots. """
        view: SbSWindow = self._view
        widget: DualPlotWidget = view.get_current_tab()[1]
        widget.clear()

# Other ------------------------------------------------------------------------
    @Slot()
    def show_settings(self):
        LOGGER.debug("Showing settings.")
        settings_dialog = SettingsDialog(settings=self.settings)
        if settings_dialog.exec_():
            view: SbSWindow = self._view
            view.update_menu_settings(
                menu="View",
                settings=self.settings.plotting,
            )
            self.plot()
        

# Helper Functions ------------------------------------------------------------

def clear_segments(segments: Sequence[SegmentDataModel]):
    """ Clear all chached segment data, so that the GUI loads the new SbS data. """
    for segment in segments:
        segment.data.clear()
