from pathlib import Path

from qtpy import QtWidgets

from omc3_gui.segment_by_segment.measurement_model import OpticsMeasurement
from omc3_gui.utils.dataclass_ui import DataClassDialog, FieldUIDef, DataClassUI

TO_BE_DEFINED = Path("to_be_defined")


class OpticsMeasurementDialog(DataClassDialog):

    WINDOW_TITLE = "Optics Measurement"
    DEFAULT_SIZE = (800, -1)
    
    def __init__(self, parent=None, optics_measurement: OpticsMeasurement = None):
        if optics_measurement is None:
            optics_measurement = OpticsMeasurement(measurement_dir=TO_BE_DEFINED, output_dir=TO_BE_DEFINED)

        dataclass_ui = DataClassUI.build_dataclass_ui(
            field_def=[
                FieldUIDef(name="measurement_dir", editable=False), 
                *(FieldUIDef(name) for name in ("model_dir", "output_dir", "accel", "beam", "year", "ring"))
            ],
            dclass=OpticsMeasurement,
        )
        dataclass_ui.model = optics_measurement
        super().__init__(dataclass_ui=dataclass_ui, parent=parent)

    @property
    def measurement(self) -> OpticsMeasurement:
        return self._dataclass_ui.model