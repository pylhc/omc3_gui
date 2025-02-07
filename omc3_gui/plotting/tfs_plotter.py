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

from qtpy.QtCore import Qt

PenStyle = Qt.PenStyle


def plot_dataframes(plot: pg.PlotWidget, dataframes: dict[str, pd.DataFrame], xcolumn: str, ycolumn: str, yerrcolumn: str, xlabel: str = None, ylabel: str = None):
    for idx, (name, df) in enumerate(dataframes.items()):
        plot_errorbar(plot, x=df[xcolumn], y=df[ycolumn], yerr=df[yerrcolumn], names=df.index, label=name, color=get_mpl_color(idx))
    
    if xlabel is not None:
        plot.setLabel("bottom", xlabel)

    if ylabel is not None:
        plot.setLabel("left", ylabel)
        
def plot_errorbar(
    plot: pg.PlotWidget,
    *,
    x: Sequence, 
    y: Sequence, 
    xerr: Sequence | None = None, 
    yerr: Sequence | None = None, 
    names: Sequence | None = None, 
    label: str | None = None,
    color: str | None = None,
    marker: str = 'o', 
    markersize: int = 10,
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
        markersize (int, optional): The markersize of the errorbar. Defaults to 10.
        linestyle (PenStyle, optional): The linestyle of the errorbar. Defaults to PenStyle.SolidLine.
    """
    curvePen = pg.mkPen(color=color, width=linewidth, style=linestyle)    
    errorbarPen = pg.mkPen(color=color, width=linewidth, style=PenStyle.SolidLine)
    
    # convert everything to numpy, as this is what pyqtgraph expects. 
    # pd.Series seems to also work for now, but will in the future 
    # need .iloc to work with indices 
    # (pyqtgraph and create_tooltips accesses items that way, for now at least).
    x = safe_convert_to_numpy(x)
    y = safe_convert_to_numpy(y)
    xerr = safe_convert_to_numpy(xerr)
    yerr = safe_convert_to_numpy(yerr)
    names = safe_convert_to_numpy(names)
    
    tooltips = create_tooltips(x, y, xerr, yerr, names, label)
    curve = pg.PlotDataItem(
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
        plot.addItem(errorbar)

    plot.addItem(curve)
    return curve, errorbar


def create_tooltips(x, y, xerr, yerr, names, label) -> list[str]:
    """
    Create a list of tooltips for a given errorbar.

    Args:
        x (Sequence): The x values of the errorbar.
        y (Sequence): The y values of the errorbar.
        xerr (Sequence): The xerr values of the errorbar.
        yerr (Sequence): The yerr values of the errorbar.
        names (Sequence): The names of the entries in the data sequence.
        label (str | None, optional): The label of the errorbar. Defaults to None.
    """
    tooltips = [""] * len(x)

     
    for index in range(len(x)):
        tooltip_text = ""
        if label is not None:
            tooltip_text += f"{label}\n"

        tooltip_text += f"x: {x[index]:.2e}"
        if xerr is not None:
            tooltip_text += f" ± {xerr[index]:.2e}"
        
        tooltip_text += f"\ny: {y[index]:.2e}"
        if yerr is not None:
            tooltip_text += f" ± {yerr[index]:.2e}"
        
        if names is not None:
            tooltip_text += f"\n{names[index]}"


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

