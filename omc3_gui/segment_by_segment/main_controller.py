from pathlib import Path
from typing import List, Sequence, Tuple
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
        self._view.sig_load_button_clicked.connect(self.open_measurements)
        self._view.sig_edit_optics_button_clicked.connect(self.edit_measurement)
        self._view.sig_list_optics_double_clicked.connect(self.edit_measurement)
        self._view.sig_list_optics_selected.connect(self.view_measurement)

        self._view.sig_new_segment_button_clicked.connect(self.new_segment)
        self._view.sig_copy_segment_button_clicked.connect(self.copy_segment)
        # self._view.sig_run_segment_button_clicked.connect(self.run_segment)
        # self._view.sig_remove_segment_button_clicked.connect(self.remove_segment)
        # self._view.sig_remove_button_clicked.connect(self.remove_measurement)
        self._view.sig_default_segments_button_clicked.connect(self.add_default_segments)
        # self._view.sig_load_segments_button_clicked.connect(self.load_segments)

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
    
    @Slot(OpticsMeasurement)
    def edit_measurement(self, measurement: OpticsMeasurement):
        LOGGER.debug(f"Opening edit dialog for {measurement.display()}.")
        dialog = OpticsMeasurementDialog(
            parent=self._view,
            optics_measurement=measurement,
        )
        if dialog.exec_():
            LOGGER.debug("Edit dialog closed. Updating measurement.")

    @Slot(tuple)
    def view_measurement(self, measurements: Sequence[OpticsMeasurement]):
        LOGGER.debug(f"Showing {len(measurements)} measurements.")
        if len(measurements) > 1:
            LOGGER.debug("More than one measurement selected.")
            return

        measurement = measurements[0]
        segment_model = SegmentTableModel()
        segment_model.add_items(measurement.segments.values())
        self._view.set_segments(segment_model)

    
    # Segments ---
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
                measurement.segments[segment.name] = segment

        self.view_measurement(selected_measurements)

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
            measurement.segments[new_segment.name] = new_segment

        self.view_measurement(selected_measurements)
    
    @Slot(tuple)
    def copy_segment(self, segments: Sequence[SegmentModel]):
        LOGGER.debug(f"Copying {len(segments)} segments.")
        selected_measurements = self._view.get_selected_measurements()
        if not selected_measurements:
            LOGGER.error("Please select at least one measurement.")
            return

        for measurement in selected_measurements:
            for segment in segments:
                new_segment = SegmentModel(f"{segment.name} - Copy", start=segment.start, end=segment.end)
                measurement.segments[new_segment.name] = new_segment
            
        self.view_measurement(selected_measurements)
