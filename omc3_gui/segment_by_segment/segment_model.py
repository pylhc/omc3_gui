from __future__ import annotations  # Together with TYPE_CHECKING: allow circular imports for type-hints
from dataclasses import dataclass, field
from typing import List, Optional, Union

from omc3_gui.utils.dataclass_ui import metafield
from omc3_gui.utils import colors
from omc3.segment_by_segment.segments import SegmentDiffs

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omc3_gui.segment_by_segment.measurement_model import OpticsMeasurement


# HTML in tooltips does not work for me, and I cannot figure out why (jdilly)
# OK = f"<font color=\"{colors.GREEN_DARK}\">✓</font>"
# NO = f"<font color=\"{colors.RED_DARK}\">✗</font>"
OK = "✓"
NO = "✗"

def not_empty(value):
    return value != ""


@dataclass
class SegmentDataModel:
    measurement: OpticsMeasurement
    name: str =            metafield("Name",  "Name of the Segment", validate=not_empty)
    start: Optional[str] = metafield("Start", "Start of the Segment", default=None, validate=not_empty)
    end: Optional[str] =   metafield("End",   "End of the Segment",   default=None, validate=not_empty)
    _data: Optional[SegmentDiffs] = None

    def __str__(self):
        return self.name

    def is_element(self):
        return is_element(self)

    def to_input_string(self):
        """ String representation of the segment as used in inputs."""
        return to_input_string(self)
    
    @property
    def data(self) -> SegmentDiffs:
        if self._data is None or self._data.directory != self.measurement.output_dir or self._data.segment_name != self.name:
            self._data = SegmentDiffs(self.measurement.output_dir, self.name)
        return self._data
    
    def has_run(self) -> bool:
        try:
            return self.data.get_path("phase_x").is_file()
        except AttributeError:
            return False

    def clear_data(self):
        self._data = None
    
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

    def id(self) -> str:
        """ Unique identifier for the measurement, used in the ItemModel. """
        return self.name + str(self.start) + str(self.end)
    
    def tooltip(self) -> str:
        """ Returns a string with information about the segment, 
        as to be used in a tool-tip.  """
        parts = [f" {OK if segment.has_run() else NO}    {segment.measurement.display()}" for segment in self.segments]
        return "Run | Contained in:\n" + "\n".join(parts)

    def is_element(self):
        return is_element(self)

    def to_input_string(self):
        """ String representation of the segment as used in inputs."""
        return to_input_string(self)
    
def compare_segments(a: Union[SegmentDataModel, SegmentItemModel], b: Union[SegmentDataModel, SegmentItemModel]):
    return a.name == b.name and a.start == b.start and a.end == b.end


# Common functions -------------------------------------------------------------

def is_element(segment: [SegmentItemModel, SegmentDataModel]):
    return segment.start is None or segment.end is None

def to_input_string(segment: [SegmentItemModel, SegmentDataModel]):
    if is_element(segment):
        return segment.name
    return f"{segment.name},{segment.start},{segment.end}"