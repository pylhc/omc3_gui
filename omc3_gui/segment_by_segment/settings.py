""" 
Segment-by-Segment: Settings
----------------------------

Global Settings for the Segment-by-Segment application.
"""
from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass, field

from omc3_gui.utils.dataclass_ui import metafield


@dataclass
class PlotSettings:
    connect_x: bool = metafield("Connect X", "Connect X axes", default=False)
    connect_y: bool = metafield("Connect Y", "Connect Y axes", default=False)
    show_legend: bool = metafield("Show Legend", "Show legend", default=True)
    forward: bool = metafield("Forward Propagation", "Show forward propagation", default=True)
    backward: bool = metafield("Backward Propagation", "Show backward propagation", default=True)

    def get_directions(self) -> tuple[str, ...]:
        return tuple(dir for dir in ["forward", "backward"] if getattr(self, dir))

@dataclass
class Settings:
    plotting: PlotSettings = field(default_factory=PlotSettings)


    @classmethod
    def load(cls, file: str | Path) -> Settings:
        pass