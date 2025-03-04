""" 
Measurement View
----------------

This module contains the view for the measurement dialog.
"""
from dataclasses import fields

from omc3_gui.segment_by_segment.measurement_model import OpticsMeasurement
from omc3_gui.ui_components.dataclass_ui import DataClassDialog, FieldUIDef, DataClassUI



class OpticsMeasurementDialog(DataClassDialog):

    WINDOW_TITLE = "Optics Measurement"
    DEFAULT_SIZE = (800, -1)
    
    def __init__(self, parent=None, optics_measurement: OpticsMeasurement | None = None):
        if optics_measurement is None:
            optics_measurement = OpticsMeasurement()

        non_editable = ("measurement_dir", )  # set by program not by user
        dataclass_ui = DataClassUI(
            field_definitions=[
                FieldUIDef(field.name, editable=field.name not in non_editable) 
                for field in fields(OpticsMeasurement) if field.name[0] != "_"
            ],
            dclass=optics_measurement,
        )
        super().__init__(dataclass_ui=dataclass_ui, parent=parent)

    @property
    def measurement(self) -> OpticsMeasurement:
        return self._dataclass_ui.model