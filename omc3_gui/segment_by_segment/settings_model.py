""" 
Segment-by-Segment: Settings
----------------------------

Global Settings for the Segment-by-Segment application.
"""
from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass, field

from omc3_gui.utils.dataclass_ui import metafield


@dataclass(slots=True)
class PlotSettings:
    connect_x: bool = metafield("Connect X", "Connect X axes.", default=False)
    connect_y: bool = metafield("Connect Y", "Connect Y axes.", default=False)
    show_legend: bool = metafield("Show Legend", "Show legend.", default=True)
    forward: bool = metafield("Forward Propagation", "Show forward propagation.", default=True)
    backward: bool = metafield("Backward Propagation", "Show backward propagation.", default=True)
    expected: bool = metafield("Expectation", "Show expected value after correction instead of correction itself.", default=False)

@dataclass(slots=True)
class Settings:
    cwd: Path = metafield("CWD", "Current working directory.", default=Path.cwd())
    autoload_segments: bool = metafield("Autoload Segments", "Automatically try to load existing segments when loading a measurement.", default=True)
    plotting: PlotSettings = field(default_factory=PlotSettings)
