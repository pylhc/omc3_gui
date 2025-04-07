""" 
Segment View
------------

This module contains the view for the segment dialog.
"""
from __future__ import annotations

from omc3_gui.segment_by_segment.segment_model import SegmentDataModel
from omc3_gui.ui_components.dataclass_ui import DataClassDialog, DataClassUI, FieldUIDef

class SegmentDialog(DataClassDialog):

    WINDOW_TITLE = "Segment Editor"
    DEFAULT_SIZE = (400, -1)
    
    def __init__(self, parent=None, segment: SegmentDataModel | None = None):
        if segment is None:
            segment = SegmentDataModel(measurement=None)  # dummy
        
        dataclass_ui = DataClassUI(
            field_definitions=[
                FieldUIDef(name) for name in ("name", "start", "end")
            ],
            dclass=segment,
        )
        super().__init__(dataclass_ui=dataclass_ui, parent=parent)
    
    @property
    def segment(self) -> SegmentDataModel:
        return self._dataclass_ui.model
