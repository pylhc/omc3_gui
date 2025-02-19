""" 
Segment-by-Segment: Settings
----------------------------

Global Settings for the Segment-by-Segment application.
"""
from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass, field, fields

from omc3_gui.ui_components.dataclass_ui import metafield

@dataclass(slots=True)
class MainSettings:
    cwd: Path = metafield("Working Directory", "Current working directory. Used for default path when opening file selection dialogs.", default=Path.cwd())
    # autoload_segments: bool = metafield("Autoload Segments", "Automatically try to load existing segments when loading a measurement.", default=True)  # TODO


@dataclass(slots=True)
class PlotSettings:
    # connect_x: bool = metafield("Connect X", "Connect X axes.", default=False)  # TODO
    # connect_y: bool = metafield("Connect Y", "Connect Y axes.", default=False)  # TODO
    show_legend: bool = metafield("Show Legend", "Show legend.", default=True)
    forward: bool = metafield("Forward Propagation", "Show forward propagation.", default=True)
    backward: bool = metafield("Backward Propagation", "Show backward propagation.", default=True)
    expected: bool = metafield("Expectation", "Show expected value after correction instead of correction itself.", default=False)

@dataclass(slots=True)
class Settings:
    main: MainSettings = field(default_factory=MainSettings)
    plotting: PlotSettings = field(default_factory=PlotSettings)
