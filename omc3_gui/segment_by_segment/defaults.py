""" 
Segment-by-Segment Defaults
---------------------------

Defaults for segment by segment.
"""
from omc3_gui.segment_by_segment.segment_model import SegmentTuple

DEFAULT_SEGMENTS =(
    SegmentTuple("IP1", "BPM.12L1", "BPM.12R1"),
    SegmentTuple("IP2", "BPM.12L2", "BPM.12R2"),
    SegmentTuple("IP5", "BPM.12L5", "BPM.12R5"),
    SegmentTuple("IP8", "BPM.12L8", "BPM.12R8"),
)