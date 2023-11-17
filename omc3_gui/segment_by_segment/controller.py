from pathlib import Path
from typing import List
from omc3_gui.utils.base_classes import Controller
from omc3_gui.utils.file_dialogs import OpenDirectoriesDialog, OpenDirectoryDialog
from omc3_gui.segment_by_segment.view import SbSWindow
from omc3_gui.segment_by_segment.model import Settings
from qtpy.QtCore import Qt, Signal, Slot
from qtpy.QtWidgets import QFileDialog
from omc3_gui.segment_by_segment.measurement_model import OpticsMeasurement
import logging
from omc3_gui.segment_by_segment.measurement_view import OpticsMeasurementDialog

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
    
    
    @Slot()
    def open_measurements(self):
        LOGGER.debug("Opening new optics measurement. Asking for folder paths.")
        filenames = OpenDirectoriesDialog(
            parent=self._view,
            caption="Select Optics Folders", 
            directory=str(self._last_selected_optics_path) if self._last_selected_optics_path else None,
        ).run_selection_dialog()

        loaded_measurements = self._view.get_measurement_list()

        LOGGER.debug(f"User selected {len(filenames)} files.")
        for filename in filenames:
            self._last_selected_optics_path = filename.parent
            LOGGER.debug(f"adding: {filename}")
            optics_measurement = OpticsMeasurement.from_path(filename)
            try:
                loaded_measurements.add_item(optics_measurement)
            except ValueError as e:
                LOGGER.error(str(e))
    
    @Slot(OpticsMeasurement)
    def edit_measurement(self, measurement: OpticsMeasurement):
        LOGGER.debug(f"Opening edit dialog for {measurement.display()}.")
        dialog = OpticsMeasurementDialog(
            parent=self._view,
            optics_measurement=measurement,
        )
        if dialog.exec_():
            LOGGER.debug("Edit dialog closed. Updating measurement.")

        

