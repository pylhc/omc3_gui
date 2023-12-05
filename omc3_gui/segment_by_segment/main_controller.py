from pathlib import Path
from typing import List, Sequence, Tuple, Union
from omc3_gui.segment_by_segment.segment_model import SegmentModel
from omc3_gui.utils.base_classes import Controller
from omc3_gui.utils.file_dialogs import OpenDirectoriesDialog, OpenDirectoryDialog
from omc3_gui.segment_by_segment.main_view import SbSWindow
from omc3_gui.segment_by_segment.main_model import SegmentTableModel, Settings
from qtpy.QtCore import Qt, Signal, Slot
from qtpy.QtWidgets import QFileDialog
from omc3_gui.segment_by_segment.measurement_model import OpticsMeasurement
import logging
from omc3_gui.segment_by_segment.measurement_view import OpticsMeasurementDialog
from omc3_gui.segment_by_segment.defaults import DEFAULT_SEGMENTS

LOGGER = logging.getLogger(__name__)

class SbSController(Controller):
    
    settings: Settings
    _view: SbSWindow   # for the IDE

    def __init__(self):
        super().__init__(SbSWindow())
        self.connect_signals()
        self.settings = Settings()
        self._last_selected_optics_path = None


    def add_measurement(self, measurement: OpticsMeasurement):
        self._view.get_measurement_list().add_item(measurement) 

    
    def connect_signals(self):
        self._view.button_load.clicked.connect(self.open_measurements)
        self._view.button_edit.clicked.connect(self.edit_measurement)
        self._view.button_remove.clicked.connect(self.remove_measurement)

        self._view.sig_list_optics_double_clicked.connect(self.edit_measurement)
        self._view.sig_list_optics_selected.connect(self.measurement_selection_changed)

        self._view.button_new_segment.clicked.connect(self.new_segment)
        self._view.button_copy_segment.clicked.connect(self.copy_segment)
        self._view.button_default_segments.clicked.connect(self.add_default_segments)
        self._view.button_remove_segment.clicked.connect(self.remove_segment)

        self._view.sig_table_segments_selected.connect(self.view_segment)
    
    # Measurements ---
    @Slot()
    def open_measurements(self):
        LOGGER.debug("Opening new optics measurement. Asking for folder paths.")
        filenames = OpenDirectoriesDialog(
            parent=self._view,
            caption="Select Optics Folders", 
            directory=str(self._last_selected_optics_path) if self._last_selected_optics_path else None,
        ).run_selection_dialog()

        loaded_measurements = self._view.get_measurement_list()
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

        self._view.set_selected_measurements(measurement_indices)
    
    @Slot()
    def edit_measurement(self, measurement: OpticsMeasurement = None):
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
        if dialog.exec_():
            LOGGER.debug("Edit dialog closed. Updating measurement.")

    @Slot()
    def remove_measurement(self, measurements: Sequence[OpticsMeasurement] = None):
        if measurements is None:
            measurements = self._view.get_selected_measurements()
            if not len(measurements):
                LOGGER.warning("No measurement selected.")
                return
        self._view.get_measurement_list().remove_items(measurements)
        self._view.set_selected_measurements()

    @Slot(tuple)
    def measurement_selection_changed(self, measurements: Sequence[OpticsMeasurement]):
        LOGGER.debug(f"Selected {len(measurements)} measurements.")
        if len(measurements) > 1:
            self._view.button_edit.setEnabled(False)
            return
        else:
            self._view.button_edit.setEnabled(True)

        measurement = measurements[0]
        segment_model = SegmentTableModel()
        segment_model.add_items(measurement.segments)
        self._view.set_segments(segment_model)

    def get_single_measurement(self) -> OpticsMeasurement:
        measurements = self._view.get_selected_measurements()
        if len(measurements) == 0:
            raise ValueError("Please select at least one measurement.")
        if len(measurements) > 1:
            raise ValueError("Please select only one measurement.")
        return measurements[0]
    
    # Segments -----------------------------------------------------------------
    @Slot(tuple)
    def view_segment(self, segments: Sequence[SegmentModel]):
        LOGGER.debug(f"Showing {len(segments)} segments.")
        if len(segments) > 1:
            LOGGER.debug("More than one segment selected. Clearing Plots.")
            return

        segment = segments[0]
        # Plot segements
    
    @Slot()
    def add_default_segments(self):
        LOGGER.debug("Adding default segments.")
        selected_measurements = self._view.get_selected_measurements()
        if not selected_measurements:
            LOGGER.error("Please select at least one measurement.")
            return

        for measurement in selected_measurements:
            beam = measurement.beam
            if beam is None:
                LOGGER.error(f"No beam found in measurement {measurement.display()}. Cannot add default segments.")
                continue

            for segment_tuple in DEFAULT_SEGMENTS:
                segment = SegmentModel(*segment_tuple)
                segment.start = f"{segment.start}.B{beam}"
                segment.end = f"{segment.end}.B{beam}"
                measurement.try_add_segment(segment)

        self.measurement_selection_changed(selected_measurements)

    @Slot()
    def new_segment(self):
        LOGGER.debug("Creating new segment.")
        selected_measurements = self._view.get_selected_measurements()
        if not selected_measurements:
            LOGGER.error("Please select at least one measurement.")
            return
        
        # add the same segment to all selected measurements! 
        # This allows for renaming it in one, and having the same name in all.
        # Might have unexpected side-effects. (jdilly)
        new_segment = SegmentModel("New Segment")  
        for measurement in selected_measurements:
            measurement.try_add_segment(new_segment)

        self.measurement_selection_changed(selected_measurements)
    
    @Slot()
    def copy_segment(self, segments: Sequence[SegmentModel] = None):
        if segments is None:
            segments = self._view.get_selected_segments()
            if not segments:
                LOGGER.error("Please select at least one segment to copy.")
                return

        LOGGER.debug(f"Copying {len(segments)} segments.")
        selected_measurements = self._view.get_selected_measurements()
        if not selected_measurements:
            LOGGER.error("Please select at least one measurement.")
            return

        for measurement in selected_measurements:
            for segment in segments:
                new_segment = SegmentModel(f"{segment.name} - Copy", start=segment.start, end=segment.end)
                measurement.try_add_segment(new_segment)
            
        self.measurement_selection_changed(selected_measurements)
    
    @Slot()
    def remove_segment(self, segments: Sequence[SegmentModel] = None):
        if segments is None:
            segments = self._view.get_selected_segments()
            if not segments:
                LOGGER.error("Please select at least one segment to remove.")
                return

        LOGGER.debug(f"Removing {len(segments)} segments.")
        selected_measurements = self._view.get_selected_measurements()
        if not selected_measurements:
            LOGGER.error("Please select at least one measurement.")
            return

        for measurement in selected_measurements:
            for segment in segments:
                measurement.try_remove_segment(segment)

        self.measurement_selection_changed(selected_measurements)
