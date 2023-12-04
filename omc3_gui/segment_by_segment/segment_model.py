from dataclasses import dataclass
from typing import Optional

@dataclass
class SegmentModel:
    name: str
    start: Optional[str] = None
    end: Optional[str] = None
    enabled: Optional[bool] = True

    def __str__(self):
        return self.name

    def is_element(self):
        return self.start is None or self.end is None

    def to_input_string(self):
        """ String representation of the segment as used in inputs."""
        if self.is_element():
            return self.name
        return f"{self.name},{self.start},{self.end}"
