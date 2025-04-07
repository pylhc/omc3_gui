""" 
Segment Model
-------------

This module contains the model for the Segments 
in the Segment-by-Segment application.
"""
from __future__ import annotations

from collections import namedtuple
from dataclasses import dataclass
from pathlib import Path
import re
from typing import TYPE_CHECKING

from omc3.segment_by_segment.segments import SegmentDiffs, EXT
from omc3.optics_measurements.constants import NAME
import tfs

from omc3_gui.ui_components import colors
from omc3_gui.ui_components.dataclass_ui import metafield
from omc3_gui.ui_components.item_models import Item

if TYPE_CHECKING:
    from omc3_gui.segment_by_segment.measurement_model import OpticsMeasurement

OK: str = f"<font color=\"{colors.GREEN_DARK}\">✓</font>"
NO: str = f"<font color=\"{colors.RED_DARK}\">✗</font>"
TO_BE_DEFINED: str = "to_be_defined"


def not_empty(value: str | None) -> bool:
    if value is None:
        return False
    value = value.strip()
    return value != "" and value != TO_BE_DEFINED


SegmentTuple = namedtuple('Segment', ['name', 'start', 'end'])  # the simplest way to store a segment definition


@dataclass(slots=True)
class SegmentDataModel:
    """" Container for the segment data, which is also used in the Segment creation dialog. """

    measurement: OpticsMeasurement
    name: str =         metafield("Name",  "Name of the Segment", default=TO_BE_DEFINED, validate=not_empty)
    start: str | None = metafield("Start", "Start of the Segment", default=None, validate=not_empty)
    end: str | None =   metafield("End",   "End of the Segment",   default=None, validate=not_empty)
    _data: SegmentDiffs | None = None

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
        # TODO: Maybe load and check first and last BPM? (jdilly, 2025)

    def clear_data(self):
        self._data = None
    
    def copy(self):
        return SegmentDataModel(measurement=self.measurement, name=self.name, start=self.start, end=self.end)


class SegmentItemModel(Item):
    """ Model for a segment item in the Segment-Table of the Segment-by-Segment application. 
    Each item has name, start and end and attached a list of actual segment-obejcts
    """

    def __init__(self, name: str, start: str = None, end: str = None):
        self._name = name
        self._start = start
        self._end = end
        self._segments: list[SegmentDataModel] = []

    @classmethod
    def from_segments(cls, segments: list[SegmentDataModel]) -> SegmentItemModel:
        new = cls(segments[0].name, segments[0].start, segments[0].end)
        new.segments = segments  # also checks for equality of given segments
        return new
    
    @classmethod
    def from_segment(cls, segment: SegmentDataModel) -> SegmentItemModel:
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
    def segments(self) -> list[SegmentDataModel]:
        return self._segments
    
    @segments.setter
    def segments(self, segments: list[SegmentDataModel]):
        if any(not compare_segments(self, segment) for segment in segments):
            raise ValueError(
                "At least one given segment has a different "
                f"definition than the others or than this {self.__class__.name}."
            )
        self._segments = segments

    def append_segment(self, segment: SegmentDataModel):
        if not compare_segments(self, segment):
            raise ValueError(f"Given segment has a different definition than this {self.__class__.name}.")
        self.segments.append(segment)

    @property
    def id(self) -> str:
        """ Unique identifier for the segment. """
        return self.name + self.start + self.end
    
    def tooltip(self) -> str:
        """ Returns a string with information about the segment, 
        as to be used in a tool-tip.  
        
        Hint: Use fully HTML compatible strings, otherwise Qt will revert to plain text. 
              e.g. use <br> instead of \\n. Also &nbsp; instead of whitespaces, as they are collapsed in HTML.
    
        """
        parts = [
            f"<tr><td>{OK if segment.has_run() else NO}</td>"
            "<td></td>"
            f"<td>{segment.measurement.display()}</td></tr>" 
            for segment in self.segments
        ]
        return "<tr><th>Run</th><th>|</th><th>In Measurement</th></tr>" + "".join(parts)

    def is_element(self):
        return is_element(self)

    def to_input_string(self):
        """ String representation of the segment as used in inputs."""
        return to_input_string(self)


# Segment functions ---

def compare_segments(a: SegmentDataModel | SegmentItemModel, b: SegmentDataModel | SegmentItemModel) -> bool:
    """ Checks if two Segments have the same definition. """
    return a.name == b.name and a.start == b.start and a.end == b.end


def is_element(segment: SegmentItemModel | SegmentDataModel) -> bool:
    """ Checks if the segment is an element-segment. """
    return segment.start is None or segment.end is None


def to_input_string(segment: SegmentItemModel | SegmentDataModel) -> str:
    """ Convert the segment to the string representation as used in inputs. """
    if is_element(segment):
        return segment.name
    return f"{segment.name},{segment.start},{segment.end}"


# Other ---

def get_segments_from_directory(directory: Path) -> list[SegmentTuple]:
    """ Parse segments from a directory. 
    
    This function needs to be kept synchronized with :class:`omc3.segment_by_segment.segments.SegmentDiffs`.
    """
    pattern = fr"{SegmentDiffs.PREFIX}.+?_[xy]_(.+)\{EXT}"  # keep in sync, hint: '.' in EXT
    segments: list[SegmentTuple] = []
    names: set[str] = set()
    for file in directory.glob(f"{SegmentDiffs.PREFIX}*{EXT}"):
        file_match = re.match(pattern, file.name)
        if file_match is None:
            continue

        name = file_match.group(1)
        if name not in names:
            names.add(name)
            df = tfs.read(file, index=NAME)
            segments.append(SegmentTuple(name, df.index[0], df.index[-1]))
    return segments