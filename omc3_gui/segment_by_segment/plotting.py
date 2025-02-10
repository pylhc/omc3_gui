""" 
Sgement-by-Segment Plots
------------------------

Plots for segment-by-segment.
"""
from __future__ import annotations

from omc3.definitions.optics import ColumnsAndLabels, S_COLUMN
from omc3_gui.plotting.classes import DualPlot
from omc3_gui.segment_by_segment.settings import PlotSettings
from omc3_gui.plotting.latex_to_html import latex_to_html_converter
from omc3_gui.plotting.tfs_plotter import plot_dataframes
from omc3_gui.segment_by_segment.segment_model import SegmentDataModel
from omc3.segment_by_segment.definitions import PropagableColumns



def plot_segment_data(widget: DualPlot, definition: ColumnsAndLabels, segments: list[SegmentDataModel], settings: PlotSettings):
    """ 
    Plot the given segments with the given definition. 
    """
    s_column = S_COLUMN
    for plane, plot in zip("xy", [widget.top, widget.bottom]): 
        data_name = f"{definition.text_label}_{plane}"  # coincides with the name in TfsCollection

        dataframes = {
            segment.measurement.display(): segment.data[data_name] 
            for segment in segments if segment.has_run()
        }
        
        plane_def = definition.set_plane(plane.upper())

        xcolumn = s_column.column
        column_def = PropagableColumns(plane_def.column, plane="")  # `.column` already contains plane

        for direction in settings.get_directions():
            if direction == "forward":
                ycolumn = column_def.forward
                yerrcolumn = column_def.error_forward
                marker = "t2"  # forward triangle >
                brightness = None

            elif direction == "backward":
                ycolumn = column_def.backward
                yerrcolumn = column_def.error_backward
                marker = "t3"  # backward triangle <
                brightness = 150  # 50% brighter

            else: 
                raise ValueError(f"Unknown direction: {direction}")

            plot_dataframes(
                plot=plot, 
                dataframes=dataframes, 
                xcolumn=xcolumn, 
                ycolumn=ycolumn, 
                yerrcolumn=yerrcolumn,
                xlabel=s_column.label,
                ylabel=latex_to_html_converter(plane_def.label),
                legend=settings.show_legend,
                brightness=brightness,
                marker=marker,
            )