""" 
Sgement-by-Segment Plots
------------------------

Plots for segment-by-segment.
"""
from __future__ import annotations

import logging

from omc3.definitions.optics import S_COLUMN, ColumnsAndLabels
from omc3.segment_by_segment.definitions import PropagableColumns
from qtpy.QtCore import Qt

from omc3_gui.plotting.classes import DualPlot
from omc3_gui.plotting.latex_to_html import latex_to_html_converter
from omc3_gui.plotting.tfs_plotter import plot_dataframes
from omc3_gui.segment_by_segment.segment_model import SegmentDataModel
from omc3_gui.segment_by_segment.settings import PlotSettings

LOGGER = logging.getLogger(__name__)


PenStyle = Qt.PenStyle



def plot_segment_data(widget: DualPlot, definition: ColumnsAndLabels, segments: list[SegmentDataModel], settings: PlotSettings):
    """ 
    Plot the given segments with the given definition. 

    Assumes all segments have been run. Please check beforehand.
    """
    s_column = S_COLUMN
    
    # use the segment name as label, if there is more than one segment from the same measurement
    use_segment_label = len(set(s.measurement.display() for s in segments)) != len(segments)
    def get_label(segment: SegmentDataModel) -> str:
        if use_segment_label:
            return f"{segment.measurement.display()} {segment.name}"
        return segment.measurement.display()

    
    for plane, plot in zip("xy", [widget.top, widget.bottom]): 
        data_name = f"{definition.text_label}_{plane}"  # coincides with the name in TfsCollection

        dataframes = {
            get_label(segment): segment.data[data_name] 
            for segment in segments
        }
        
        plane_def = definition.set_plane(plane.upper())

        xcolumn = s_column.column
        column_def = PropagableColumns(plane_def.column, plane="")  # `.column` already contains plane

        for direction in ("forward", "backward"):
            if not getattr(settings, direction):
                continue

            for expected in (None, settings.expected):
                # note: don't really like the way the following settings are handled, 
                # but lack a better idea (jdilly, 2025) 
                
                column_name = direction
                suffix = ""
                linestyle = PenStyle.SolidLine
                shorthand = "fwd" if direction == "forward" else "bwd"
                marker = "t2" if direction == "forward" else "t3"  # triangle forward > or backward <
                brightness = None if direction == "forward" else 150  # 50% brighter for backwards

                if expected is not None:
                    column_name = f"{direction}_{'expected' if expected else 'correction'}"
                    suffix = " expct" if expected else " corr"
                    linestyle = PenStyle.DashLine

                plot_dataframes(
                    plot=plot, 
                    dataframes=dataframes, 
                    xcolumn=xcolumn, 
                    ycolumn=getattr(column_def, column_name),
                    yerrcolumn=getattr(column_def, f"error_{column_name}"),
                    xlabel=s_column.label,
                    ylabel=latex_to_html_converter(plane_def.label),
                    legend=settings.show_legend,
                    marker=marker,
                    markersize=settings.marker_size,
                    brightness=brightness,
                    linestyle=linestyle,
                    suffix=f" ({shorthand}{suffix})",
                )

        if settings.reset_zoom:
            plot.enableAutoRange()
