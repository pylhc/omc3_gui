""" 
Plotting
--------

Plots for segment-by-segment.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cache
import logging
from pathlib import Path

from omc3.definitions.optics import (
    S_COLUMN,
    S_MODEL_COLUMN,
    RDT_AMPLITUDE_COLUMN, 
    RDT_PHASE_COLUMN,
    RDT_REAL_COLUMN,
    RDT_IMAG_COLUMN,
    ColumnsAndLabels,
)
from omc3.segment_by_segment.propagables import PropagableColumns
from omc3.model.constants import TWISS_ELEMENTS_DAT
from omc3.optics_measurements.constants import NAME
from qtpy.QtCore import Qt
import tfs

from omc3_gui.plotting.classes import DualPlotWidget
from omc3_gui.plotting.element_lines import plot_element_lines
from omc3_gui.plotting.latex_to_html import latex_to_html_converter
from omc3_gui.plotting.tfs_plotter import plot_dataframes
from omc3_gui.segment_by_segment.segment_model import SegmentDataModel
from omc3_gui.segment_by_segment.settings import PlotSettings

LOGGER = logging.getLogger(__name__)


PenStyle = Qt.PenStyle

@dataclass(frozen=True)
class PlotDefinition:
    file_name: str
    ylabel: str
    column: str 
    error_column: str
    propagable_columns: PropagableColumns

    @classmethod
    def create(cls, file_name: str, columns: ColumnsAndLabels):
        return cls(
                file_name=file_name,
                ylabel=latex_to_html_converter(columns.delta_label),
                column=columns.column,
                error_column=columns.error_column,
                propagable_columns=PropagableColumns(columns.column, plane="")
            
        )


@dataclass(frozen=True)
class DualPlotDefinition:
    name: str
    top: PlotDefinition
    bottom: PlotDefinition

    @property
    def plots(self) -> tuple[PlotDefinition, PlotDefinition]:
        return (self.top, self.bottom)

    @classmethod
    def generate_xy(cls, name: str, file_name: str, columns: ColumnsAndLabels):
        """ Generate a DualPlotDefinition for XY-Planed Plots. """
        return cls(name, *(
            PlotDefinition.create(f"{file_name}_{plane}", columns.set_plane(plane.upper())) for plane in "xy"
        ))
    
    @classmethod
    def generate_amplitude_phase(cls, file_name: str):
        """ Generate a DualPlotDefinition for Amplitude/Phase Plots. """
        name = f"{file_name} A/φ"
        amp = RDT_AMPLITUDE_COLUMN.set_label_formatted(file_name)
        phase = RDT_PHASE_COLUMN.set_label_formatted(file_name)
        return cls.generate_rdt(name, file_name, amp, phase)
    
    @classmethod
    def generate_real_imag(cls, file_name: str):
        """ Generate a DualPlotDefinition for Amplitude/Phase Plots. """
        name = f"{file_name} Re/Im"
        real = RDT_REAL_COLUMN.set_label_formatted(file_name)
        imag = RDT_IMAG_COLUMN.set_label_formatted(file_name)
        return cls.generate_rdt(name, file_name, real, imag)

    @classmethod
    def generate_rdt(cls, name: str, file_name: str,  columns_top: ColumnsAndLabels, columns_bottom: ColumnsAndLabels):
        """ Generate a DualPlotDefintion for RDTs, i.e. Amplitude/Phase, Re/Im. """
        return cls(name, *(
            PlotDefinition.create(file_name, columns) for columns in (columns_top, columns_bottom)
        ))


class DirectionStyle:
    """ Helper Class to define the Style based on direction and expected. """

    def __init__(self, direction: str, expected: bool | None):
        self.direction = direction
        self.expected = expected

    @property
    def linestyle(self):
        if self.expected is None:
            return PenStyle.SolidLine
        return PenStyle.DashLine

    @property
    def brightness(self):
        return {
            "forward": None,
            "backward": 150
        }[self.direction]

    @property
    def marker(self):
        return {
            "forward": "t2",
            "backward": "t3"
        }[self.direction]

    @property
    def suffix(self):
        shorthand = {
            "forward": " fwd",
            "backward": " bwd"
        }[self.direction]
        return {
            None: shorthand,
            True: f"{shorthand} expct",
            False: f"{shorthand} corr"
        }[self.expected]

    @property
    def column(self):
        return {
            None: self.direction,
            True: f"{self.direction}_expected",
            False: f"{self.direction}_correction"
        }[self.expected]

    @property
    def error_column(self):
        return f"error_{self.column}"


# Plotting ---------------------------------------------------------------------

def plot_segment_data(
    widget: DualPlotWidget, 
    definitions: DualPlotDefinition, 
    segments: list[SegmentDataModel], 
    settings: PlotSettings
    ):
    """ Plot the given segments with the given definition. """
    # use the segment name as label, if there is more than one segment from the same measurement
    use_segment_label = len(set(s.measurement.display() for s in segments)) != len(segments)
    def get_label(segment: SegmentDataModel) -> str:
        if use_segment_label:
            return f"{segment.measurement.display()} {segment.name}"
        return segment.measurement.display()

    # wrap loading for better error handling and logging
    def get_data(segment: SegmentDataModel, file_name: str):
        try:
            return segment.data[file_name]
        except FileNotFoundError:
            LOGGER.error(f"Segment {segment.name} has no data for {file_name}.")
            return None
    
    # set x column 
    x_column = S_COLUMN
    if settings.model_s:
        x_column = S_MODEL_COLUMN

    # Loop over top/bottom plots ---
    for definition, plot in zip(definitions.plots, widget.plots):
        definition: PlotDefinition

        dataframes = {
            get_label(segment): get_data(segment, definition.file_name) 
            for segment in segments
        }

        if any(df is None for df in dataframes.values()):
            LOGGER.error("Could not find data for all segments, please run these again !?")
            # continue anyway
            dataframes = {label: df for label, df in dataframes.items() if df is not None}

        # Plot Model Elements ---
        if settings.show_model:
            model_dir = segments[0].measurement.model_dir
            bpm_ranges = [(s.start, s.end) for s in segments]
            plot_element_lines(
                plot=plot,
                data_frame=load_twiss_elements(model_dir),
                ranges=bpm_ranges,
                start_zero=not settings.model_s,
            )

        # Loop over forward/backward plots ---
        for direction in ("forward", "backward"):
            if not getattr(settings, direction):  # user activated
                continue
            
            # Loop over propagaed/expected or corrected values --- 
            for expected in (None, settings.expected):
                style = DirectionStyle(direction, expected)

                # Now put it all together ---
                plot_dataframes(
                    plot=plot, 
                    dataframes=dataframes, 
                    xcolumn=x_column.column, 
                    ycolumn=getattr(definition.propagable_columns, style.column),
                    yerrcolumn=getattr(definition.propagable_columns, style.error_column),
                    xlabel=x_column.label,
                    ylabel=definition.ylabel,
                    legend=settings.show_legend,
                    marker=style.marker,
                    markersize=settings.marker_size,
                    brightness=style.brightness,
                    linestyle=style.linestyle,
                    suffix=style.suffix,
                )

        if settings.reset_zoom:
            plot.enableAutoRange()


@cache
def load_twiss_elements(model_dir: Path) -> tfs.TfsDataFrame:
    """ Load the twiss elements from the model directory. 
    Cache here, because that might take a moment, so better to keep the DataFrame in memory.
    """
    df = tfs.read_tfs(model_dir / TWISS_ELEMENTS_DAT, index=NAME)
    df = df.loc[df.index.str.match(r"^(?!DRIFT).*"), [S_COLUMN.column]]  # we actually only need the s column and headers
    return df
