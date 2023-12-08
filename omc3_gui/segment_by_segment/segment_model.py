from __future__ import annotations  # Together with TYPE_CHECKING: allow circular imports for type-hints
from dataclasses import dataclass
from typing import List, Optional, Union

from omc3_gui.utils.dataclass_ui import metafield
from omc3_gui.utils import colors

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omc3_gui.segment_by_segment.measurement_model import OpticsMeasurement



OK = f"<span color=\"{colors.GREEN_DARK}\">✓</span>"
NO = f"<span color=\"{colors.RED_DARK}\">✗</span>"

def not_empty(value):
    return value != ""


@dataclass
class SegmentDataModel:
    measurement: OpticsMeasurement
    name: str =            metafield("Name",  "Name of the Segment", validate=not_empty)
    start: Optional[str] = metafield("Start", "Start of the Segment", default=None, validate=not_empty)
    end: Optional[str] =   metafield("End",   "End of the Segment",   default=None, validate=not_empty)
    _data: Optional[dict] = None

    def __str__(self):
        return self.name

    def is_element(self):
        return self.start is None or self.end is None

    def to_input_string(self):
        """ String representation of the segment as used in inputs."""
        if self.is_element():
            return self.name
        return f"{self.name},{self.start},{self.end}"
    
    def has_run(self) -> bool:
        return bool(self._data)

    def copy(self):
        return SegmentDataModel(measurement=self.measurement, name=self.name, start=self.start, end=self.end)


class SegmentItemModel:

    def __init__(self, name: str, start: str = None, end: str = None):
        self._name = name
        self._start = start
        self._end = end
        self._segments = []

    @classmethod
    def from_segments(cls, segments: List[SegmentDataModel]) -> "SegmentItemModel":
        new = cls(segments[0].name, segments[0].start, segments[0].end)
        new.segments = segments  # also checks for equality of given segments
        return new
    
    @classmethod
    def from_segment(cls, segment: SegmentDataModel) -> "SegmentItemModel":
        new = cls(segment.name, segment.start, segment.end)
        return new

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str):
        self._name = value
        for segment in self.segments:
            segment.name = value
    
    @property
    def start(self) -> str:
        return self._start

    @start.setter
    def start(self, value: str):
        self._start = value
        for segment in self.segments:
            segment.start = value

    @property
    def end(self) -> str:
        return self._end

    @end.setter
    def end(self, value: str):
        self._end = value
        for segment in self.segments:
            segment.end = value

    @property
    def segments(self) -> List[SegmentDataModel]:
        return self._segments
    
    @segments.setter
    def segments(self, segments: List[SegmentDataModel]):
        if any(not compare_segments(self, segment) for segment in segments):
            raise ValueError(
                "At least one given segment has a different "
                "definition than the others or than this {self.__class__.name}."
            )
        self._segments = segments

    def append_segment(self, segment: SegmentDataModel):
        if not compare_segments(self, segment):
            raise ValueError(f"Given segment has a different definition than this {self.__class__.name}.")
        self.segments.append(segment)
    
    @property
    def id(self) -> str:
        """ Unique identifier for the measurement, used in the ItemModel. """
        return self.name + str(self.start) + str(self.end)
    
    def tooltip(self) -> str:
        """ Returns a string with information about the segment, 
        as to be used in a tool-tip.  """
        parts = [f"{OK if segment.has_run() else NO}   {segment.measurement.display()}" for segment in self.segments]
        return "Run | Contained in:\n" + "\n".join(parts)

def compare_segments(a: Union[SegmentDataModel, SegmentItemModel], b: Union[SegmentDataModel, SegmentItemModel]):
    return a.name == b.name and a.start == b.start and a.end == b.end

