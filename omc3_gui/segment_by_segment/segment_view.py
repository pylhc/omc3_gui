from pathlib import Path

from qtpy import QtWidgets

from omc3_gui.segment_by_segment.segment_model import SegmentDataModel
from omc3_gui.utils.dataclass_ui import DataClassDialog, DataClassUI, FieldUIDef


TO_BE_DEFINED = "to_be_defined"

class SegmentDialog(DataClassDialog):

    WINDOW_TITLE = "Segment Editor"
    DEFAULT_SIZE = (400, -1)
    
    def __init__(self, parent=None, segment: SegmentDataModel = None):
        if segment is None:
            segment = SegmentDataModel(name=TO_BE_DEFINED, measurement=None)  # dummy
        
        dataclass_ui = DataClassUI.build_dataclass_ui(
            field_definitions=[
                FieldUIDef(name) for name in ("name", "start", "end")
            ],
            dclass=SegmentDataModel,
        )
        dataclass_ui.model = segment
        super().__init__(dataclass_ui=dataclass_ui, parent=parent)
    
    @property
    def segment(self) -> SegmentDataModel:
        return self._dataclass_ui.model
