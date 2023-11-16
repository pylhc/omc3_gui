from pathlib import Path

from qtpy import QtWidgets

from omc3_gui.segment_by_segment.measurement_model import OpticsMeasurement
from omc3_gui.utils.dataclass_ui import DataClassUI, FieldUIDef, dataclass_ui_builder

TO_BE_DEFINED = Path("to_be_defined")


class OpticsMeasurementDialog(QtWidgets.QDialog):
    
    def __init__(self, parent=None, optics_measurement: OpticsMeasurement = None):
        super().__init__(parent)
        self._button_ok: QtWidgets.QPushButton = None
        self._button_cancel: QtWidgets.QPushButton = None
        self._button_box: QtWidgets.QDialogButtonBox = None
        self._dataclass_ui: DataClassUI = None

        self._build_gui()
        self._connect_signals()
        self._set_size(width=800)

        
        if optics_measurement is None:
            self.optics_measurement = OpticsMeasurement(measurement_dir=TO_BE_DEFINED, output_dir=TO_BE_DEFINED)
        else:
            # make this a copy? let the outside handle updates?
            self.optics_measurement = optics_measurement

        self._update_ui()

    def _set_size(self, width: int = -1, height: int = -1):
        # Set position to the center of the parent
        parent = self.parent()
        if parent is not None:
            parent_geo = parent.geometry()
            parent_pos = parent.mapToGlobal(parent.pos())  # multiscreen support
            if width >= 0:
                x = parent_pos.x() + parent_geo.width() / 2
            else:
                x = parent_pos.x() + (parent_geo.width() - width) / 2

            if height >=0 :
                y = parent_pos.y() + parent_geo.height() / 2
            else:
                y = parent_pos.y() + (parent_geo.height() - height) / 2
            self.move(x, y)
        
        # Set size
        self.resize(width, height)


    def _build_gui(self):
        self.setWindowTitle("Optics Measurement")
        layout = QtWidgets.QVBoxLayout()

        # A little bit of coupling to the model here, 
        # so if field-names change or are added this needs to be adjusted.
        # But it makes more sense to have this list here than in the model.
        self._dataclass_ui = dataclass_ui_builder(
            field_def=[
                FieldUIDef(name="measurement_dir", editable=False), 
                *(FieldUIDef(name) for name in ("output_dir", "accel", "beam", "year", "ring"))
            ],
            dclass=OpticsMeasurement,
        )
        layout.addLayout(self._dataclass_ui.layout)

        QBtn = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        self._button_box = QtWidgets.QDialogButtonBox(QBtn)
        layout.addWidget(self._button_box)

        self.setLayout(layout)

    def _update_ui(self): 
        self._dataclass_ui.model = self.optics_measurement
        self._dataclass_ui.update_ui()  # changes labels to red
        self._dataclass_ui.reset_labels()

    def accept(self):
        self._dataclass_ui.update_model()
        super().accept() 

    def _connect_signals(self):
        self._button_box.accepted.connect(self.accept)
        self._button_box.rejected.connect(self.reject)
        

