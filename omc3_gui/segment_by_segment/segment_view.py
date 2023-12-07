from pathlib import Path

from qtpy import QtWidgets

from omc3_gui.segment_by_segment.segment_model import SegmentModel
from omc3_gui.utils.dataclass_ui import DataClassDialog, DataClassUI, FieldUIDef


TO_BE_DEFINED = "to_be_defined"

class SegmentDialog(DataClassDialog):

    WINDOW_TITLE = "Segment Editor"
    DEFAULT_SIZE = (400, -1)
    
    def __init__(self, parent=None, segment: SegmentModel = None):
        if segment is None:
            segment = SegmentModel(name=TO_BE_DEFINED)
        
        dataclass_ui = DataClassUI.build_dataclass_ui(
            field_def=[
                FieldUIDef(name) for name in ("name", "start", "end")
            ],
            dclass=SegmentModel,
        )
        dataclass_ui.model = segment
        super().__init__(dataclass_ui=dataclass_ui, parent=parent)
    
    @property
    def segment(self) -> SegmentModel:
        return self._dataclass_ui.model
