""" 
Element Line Plotter
--------------------

This module contains functions to plot element lines with pyqtgraph.
"""
import numpy as np
import tfs
import pyqtgraph as pg
import logging
from omc3.optics_measurements.constants import S
from qtpy.QtCore import Qt

LOGGER = logging.getLogger(__name__)
LENGTH: str = "LENGTH"

def plot_element_lines(plot: pg.PlotWidget, data_frame: tfs.TfsDataFrame, ranges: list[tuple[str, str]], start_zero: bool): 
    """ 
    Plot vertical lines on the plot for elements in the data_frame in the given ranges.

    Args:
        plot (pg.PlotWidget): The plot to plot the lines into.
        data_frame (tfs.TfsDataFrame): The data_frame to plot the lines from.
        ranges (list[tuple[str, str]]): A list of tuples of the form (start_element, end_element).
        start_zero (bool): Whether to start the plot from zero or not.  
    """
    if start_zero and not all(ranges[0][0] == r[0] for r in ranges):
        LOGGER.warning("Not all ranges start at the same element. Using only the first!")
        ranges = [ranges[0]]

    plotItem = plot.plotItem

    # Find start and end elements
    start = min(ranges, key=lambda r: data_frame.loc[r[0], S])[0]
    end = max(ranges, key=lambda r: data_frame.loc[r[1], S])[1]

    # Select element range and do some wrapping gymnastics if needed
    if data_frame.loc[start, S] <= data_frame.loc[end, S]:
        s_elements = data_frame.loc[start:end, S]
    else:
        s_elements = data_frame.loc[start:, S] + data_frame.loc[:end, S]
    
    if start_zero:
        s_elements = s_elements - s_elements.loc[start]
        s_elements = s_elements + np.where(s_elements < 0, data_frame.headers[LENGTH], 0)

    # Plot the lines - this takes a while, not sure how to improve
    plotItem.disableAutoRange()  # speeds it up a bit
    pen = pg.mkPen(color="grey", width=1, style=Qt.PenStyle.DotLine)
    for element, x in s_elements.items():
        plotItem.addLine(x=x, z=-10, pen=pen, label=element, labelOpts={"angle": 90})

