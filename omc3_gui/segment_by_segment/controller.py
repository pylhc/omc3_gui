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

LOG = logging.getLogger(__name__)

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
    
    
    @Slot()
    def open_measurements(self):
        LOG.debug("OpenButton Clicked. Asking for folder paths.")
        filenames = OpenDirectoriesDialog(
            parent=self._view,
            caption="Select Optics Folders", 
            directory=str(self._last_selected_optics_path) if self._last_selected_optics_path else None,
        ).run_selection_dialog()

        loaded_measurements = self._view.get_measurement_list()

        LOG.debug(f"User selected {len(filenames)} files.")
        for filename in filenames:
            self._last_selected_optics_path = filename.parent
            LOG.debug(f"User selected: {filename}")
            optics_measurement = OpticsMeasurement.from_path(filename)
            try:
                loaded_measurements.add_item(optics_measurement)
            except ValueError as e:
                LOG.error(str(e))
        

