""" 
TFS Plotter
-----------

This module contains functions to plot TFS dataframes with pyqtgraph.
"""
from collections.abc import Sequence

import numpy as np
import pandas as pd
import pyqtgraph as pg
from omc3.plotting.utils.colors import get_mpl_color
import logging

from qtpy.QtCore import Qt
from qtpy.QtGui import QColor

from omc3_gui.plotting.classes import ObservablePlotDataItem, YAXES_WIDTH

PenStyle = Qt.PenStyle

LOGGER = logging.getLogger(__name__)


def plot_dataframes(
    plot: pg.PlotWidget, 
    dataframes: dict[str, pd.DataFrame], 
    xcolumn: str, 
    ycolumn: str, 
    xerrcolumn: str = None,
    yerrcolumn: str = None,
    xlabel: str = None, 
    ylabel: str = None,
    legend: bool = True,
    brightness: int | None = None,
    marker: str = 'o',
    markersize: float = 6,
    linestyle: PenStyle = PenStyle.SolidLine,
    suffix: str = "",
    ):
    """ 
    Plot a collection of DataFrames with pyqtgraph.

    Args:
        plot (pg.PlotWidget): The plot to plot the dataframes into.
        dataframes (dict[str, pd.DataFrame]): A dictionary of DataFrames to plot.
        xcolumn (str): The name of the column to plot on the x-axis.
        ycolumn (str): The name of the column to plot on the y-axis.
        xerrcolumn (str): The name of the column to plot as horizontal errorbars.
        yerrcolumn (str): The name of the column to plot as vertical errorbars.
        xlabel (str): The label of the x-axis.
        ylabel (str): The label of the y-axis.
        legend (bool, optional): Whether to add a legend to the plot. Defaults to True.
        brightness (int, optional): The brightness of the colors to use. Defaults to None.
        marker (str, optional): The marker to use for the data points. Defaults to 'o'.
        markersize (float, optional): The size of the markers to use for the data points. Defaults to 6.
        linestyle (PenStyle, optional): The linestyle to use for the data points. Defaults to PenStyle.SolidLine.
        suffix (str, optional): The suffix to add to the legend. Defaults to "".
    """
    plot_item: pg.PlotItem = plot.plotItem
    
    plot_item.addLegend(offset=(0, 0))
    
    for idx, (name, df) in enumerate(dataframes.items()):
        color = pg.Color(get_mpl_color(idx))
        if brightness is not None:
            color = color.lighter(brightness)
        
        try:
            df[ycolumn]
        except KeyError:
            LOGGER.debug(f"Could not find column '{ycolumn}' in DataFrame for '{name}'. Skipping!")
            continue

        plot_errorbar(
            plot_item, 
            x=df[xcolumn], 
            y=df[ycolumn], 
            xerr=df.get(xerrcolumn), 
            yerr=df.get(yerrcolumn), 
            names=df.index, 
            label=f"{name}{suffix}", 
            color=color,
            marker=marker,
            markersize=markersize,
            linestyle=linestyle,
        )
    
    if xlabel is not None:
        plot_item.setLabel("bottom", xlabel)

    if ylabel is not None:
        plot_item.setLabel("left", ylabel)
        
    plot_item.getAxis("left").setWidth(YAXES_WIDTH)  # keep constant
    plot_item.legend.setVisible(legend)


def plot_errorbar(
    plot: pg.PlotItem,
    *,
    x: Sequence, 
    y: Sequence, 
    xerr: Sequence | None = None, 
    yerr: Sequence | None = None, 
    names: Sequence | None = None, 
    label: str | None = None,
    color: str | pg.Color | None = None,
    marker: str = 'o', 
    markersize: float = 6,
    linestyle: PenStyle = PenStyle.SolidLine,
    linewidth: float = 2,
    ) -> tuple[pg.PlotDataItem, pg.ErrorBarItem]:
    """ 
    Plot a single errorbar with pyqtgraph.
    This tries to imitate the behavior of matplotlib's errorbar function, 
    and the naming is mostly borrowed from there.

    Args:
        plot (pg.PlotWidget): The plot to plot the errorbar into.
        x (Sequence): The x values of the errorbar.
        y (Sequence): The y values of the errorbar.
        xerr (Sequence): The xerr values of the errorbar.
        yerr (Sequence): The yerr values of the errorbar.
        names (Sequence): The names of the entries in the data sequence.
        label (str | None, optional): The label of the errorbar. Defaults to None.
        color (str | None, optional): The color of the errorbar. Defaults to None.
        marker (str, optional): The marker of the errorbar. Defaults to 'o'.
        markersize (float, optional): The markersize of the errorbar. Defaults to 10.
        linestyle (PenStyle, optional): The linestyle of the errorbar. Defaults to PenStyle.SolidLine.
        linewidth (float, optional): The linewidth of the errorbar. Defaults to 2.
    """

    curvePen = pg.mkPen(color=color, width=linewidth, style=linestyle)    
    errorbarPen = pg.mkPen(color=color, width=linewidth, style=PenStyle.SolidLine)
    
    # convert everything to numpy, as this is what pyqtgraph expects. 
    # pd.Series seems to also work for now, but raises deprecation warnings, 
    # as in the future it needs .iloc to work with indices, 
    # yet pyqtgraph and create_tooltips access items via `[ ]` (for now at least).
    x = safe_convert_to_numpy(x)
    y = safe_convert_to_numpy(y)
    xerr = safe_convert_to_numpy(xerr)
    yerr = safe_convert_to_numpy(yerr)
    names = safe_convert_to_numpy(names)

    hex_color = None
    if color is not None:
        hex_color = curvePen.color().name(QColor.NameFormat.HexRgb)
    
    tooltips = create_tooltips(x, y, xerr, yerr, names, label, hex_color)
    curve = ObservablePlotDataItem(
        x=x, y=y, data=tooltips,
        name=label,
        pen=curvePen, 
        tip=None,
        symbol=marker, symbolBrush=color, symbolSize=markersize
    )
    # curve.sigPointsHovered.connect(hovered)
    # curve.sigPointsClicked.connect(clicked)
    curve.scatter.opts['hoverable'] = True
    curve.scatter.sigHovered.connect(hovered)
    
    errorbar = None
    if xerr is not None or yerr is not None:
        errorbar = pg.ErrorBarItem(
            x=x, y=y, data=tooltips, 
            width=2*xerr if xerr is not None else None, 
            height=2*yerr if yerr is not None else None, 
            pen=errorbarPen
        )
        
        # Connect errorbar and curve's visibility
        curve.visibilityChanged.connect(errorbar.setVisible)
        plot.addItem(errorbar)

    plot.addItem(curve)
    return curve, errorbar


def create_tooltips(x, y, xerr, yerr, names, label, color) -> list[str]:
    """
    Create a list of tooltips for a given errorbar.

    Args:
        x (Sequence): The x values of the errorbar.
        y (Sequence): The y values of the errorbar.
        xerr (Sequence): The xerr values of the errorbar.
        yerr (Sequence): The yerr values of the errorbar.
        names (Sequence): The names of the entries in the data sequence.
        label (str | None, optional): The label of the errorbar
        color (str | None, optional): The color of the tooltip background
    """
    tooltips = [""] * len(x)

     
    for index in range(len(x)):
        tooltip_text = "<html>"

        if color is not None:
            tooltip_text +=  "" # TODO

        if label is not None:
            tooltip_text += f"{label}<br>"

        tooltip_text += f"x: {x[index]:.2e}"
        if xerr is not None:
            tooltip_text += f" ± {xerr[index]:.2e}"
        
        tooltip_text += f"<br>y: {y[index]:.2e}"
        if yerr is not None:
            tooltip_text += f" ± {yerr[index]:.2e}"
        
        if names is not None:
            tooltip_text += f"<br>{names[index]}"
        
        if color is not None:
            tooltip_text += ""
            
        tooltip_text += "</html>"

        tooltips[index] = tooltip_text
    return tooltips


def safe_convert_to_numpy(data: Sequence | None) -> list:
    if data is None:
        return None
    
    # check if data is even iterable
    try:
        return data.to_numpy()
    except AttributeError:
        return np.array(data)

def hovered(item, points, ev):
    if not len(points):
        item.setToolTip(None)
        return
    item.setToolTip(points[0].data())


def clicked(item, points, ev):
    # print('clicked')
    pass

