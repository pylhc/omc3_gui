from dataclasses import dataclass
from typing import Optional

from omc3_gui.utils.dataclass_ui import metafield


def not_empty(value):
    return value != ""


@dataclass
class SegmentModel:
    name: str =            metafield("Name",  "Name of the Segment", validate=not_empty)
    start: Optional[str] = metafield("Start", "Start of the Segment", default=None, validate=not_empty)
    end: Optional[str] =   metafield("End",   "End of the Segment",   default=None, validate=not_empty)

    def __str__(self):
        return self.name

    def is_element(self):
        return self.start is None or self.end is None

    def to_input_string(self):
        """ String representation of the segment as used in inputs."""
        if self.is_element():
            return self.name
        return f"{self.name},{self.start},{self.end}"

    def copy(self):
        return SegmentModel(name=self.name, start=self.start, end=self.end)

    @property
    def id(self) -> str:
        """ Unique identifier for the measurement, used in the ItemModel. """
        return self.name