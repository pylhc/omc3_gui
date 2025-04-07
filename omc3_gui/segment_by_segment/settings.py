"""
Settings
--------

Global Settings for the Segment-by-Segment application.
"""
from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass, field

from omc3_gui.ui_components.dataclass_ui import metafield

@dataclass(slots=True)
class MainSettings:
    cwd: Path = metafield("Working Directory", "Current working directory. Used for default path when opening file selection dialogs.", default=Path.cwd())
    autoload_segments: bool = metafield("Autoload Segments", "Automatically try to load existing segments when loading a measurement.", default=True) 
    autodefault_segments: bool = metafield("Auto-Add Default Segments", "Automatically add default segments when loading a measurement.", default=False) 
    suggest_correctors: bool = metafield("Suggest Correctors", "Suggest correctors when editing a new correction file.", default=True)

@dataclass(slots=True)
class PlotSettings:
    show_model: bool = metafield("Show Model", "Show markers for the elements of the Model.", default=False)
    show_legend: bool = metafield("Show Legend", "Show legend.", default=True)
    marker_size: float = metafield("Marker Size", "Size of the markers.", default=8.5)
    expected: bool = metafield("Expectation", "Show expected value after correction instead of correction itself.", default=False)
    forward: bool = metafield("Forward Propagation", "Show forward propagation.", default=True)
    backward: bool = metafield("Backward Propagation", "Show backward propagation.", default=False)
    connect_x: bool = metafield("Connect X", "Connect X axes of the two plots.", default=True)
    connect_y: bool = metafield("Connect Y", "Connect Y axes of the two plots.", default=False)
    reset_zoom: bool = metafield("Reset Zoom", "Reset zoom when changing segments.", default=True)
    same_start: bool = metafield("Same Segment Start", "Plot only if the selected segments all have the same starting BPM.", default=True)
    model_s: bool = metafield("Model Location", "Use the model longitudinal location instead of the segment location.", default=False)


@dataclass(slots=True)
class Settings:
    main: MainSettings = field(default_factory=MainSettings)
    plotting: PlotSettings = field(default_factory=PlotSettings)
