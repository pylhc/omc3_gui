""" 
Classes
-------

Containers for figures, plots, etc.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
import numpy as np
import pyqtgraph as pg
from accwidgets.graph import StaticPlotWidget
from accwidgets.graph.widgets.plotitem import ExViewBox
from accwidgets.graph.widgets.plotwidget import GridOrientationOptions
from qtpy.QtCore import Signal, Qt

if TYPE_CHECKING:
    from pyqtgraph.GraphicsScene import mouseEvents
    from qtpy.QtWidgets import QGraphicsSceneMouseEvent

YAXES_WIDTH: int = 60

class ObservablePlotDataItem(pg.PlotDataItem):
    """A PlotDataItem that emits a signal when visibility changes."""
    visibilityChanged = Signal(bool)

    def setVisible(self, visible):
        super().setVisible(visible)
        self.visibilityChanged.emit(visible)


class DualPlotWidget(pg.LayoutWidget):
    """ A widget containing and handling two plots stacked vertically. """
    
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        pg.setConfigOptions(antialias=True)  # not sure if best place here

        self.top = PlotWidget()
        self.bottom = PlotWidget()

        self.addWidget(self.top, row=0, col=0)
        self.addWidget(self.bottom, row=1, col=0)

        # set margins, so the axes line up
        for plot in (self.top, self.bottom):
            plot.setContentsMargins(0, 0, 0, 0)
            plot.plotItem.getAxis("left").setWidth(YAXES_WIDTH)  # keep constant

    @property
    def plots(self) -> tuple[pg.PlotWidget, pg.PlotWidget]:
        return (self.top, self.bottom)

    def clear(self) -> None:    
        for plot in self.plots:
            plot.clear()
            plot.enableAutoRange()
    
    def set_connect_x(self, connect: bool) -> None:
        if connect:
            self.top.setXLink(self.bottom)
        else:
            self.top.setXLink(None)
            self.bottom.setXLink(None)

    def set_connect_y(self, connect: bool) -> None:
        if connect:
            self.top.setYLink(self.bottom)
        else:
            self.top.setYLink(None)
            self.bottom.setYLink(None)


class PlotWidget(StaticPlotWidget):
    """ A widget containing and handling a single plot. 
    
    Adds the look-and-feel for our omc3 guis to the default accwidgets plotwidget. 
    """
    
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, viewBox=ZoomingViewBox())  # using viewbox here requires accwidgets >= 3.0.11
        self.setBackground("w")
        self._set_show_grid(GridOrientationOptions.Both)


class ZoomingViewBox(ExViewBox):
    """ ViewBox that imitates the behavior of the Java-GUI a bit more closely than the default. """
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setMouseMode(ZoomingViewBox.RectMode)  # mode that makes zooming rectangles

    # Look and Feel ------------------------------------------------------------
    def suggestPadding(self, axis):
        """ Suggests padding (between the data and the axis) for the autoRange function. 
        For our purposes, we do not want any padding on the x-axis. """
        if axis == 0:
            return 0.0  # disable padding for x axis
        return super().suggestPadding(axis)

    # Mouse Events -------------------------------------------------------------
    def mouseClickEvent(self, ev: mouseEvents.MouseClickEvent):
        if ev.button() == Qt.MouseButton.MiddleButton:
            ev.accept()
            self.auto_zoom()
            return 

        if ev.button() == Qt.MouseButton.RightButton:
            ev.accept()
            if ev.modifiers() == Qt.KeyboardModifier.AltModifier:
                self.raiseContextMenu(ev)
                return

            self.undo_zoom(reset=ev.modifiers() == Qt.KeyboardModifier.ShiftModifier)
            return

        super().mouseClickEvent(ev)
        
    def mouseDoubleClickEvent(self, ev: QGraphicsSceneMouseEvent):
        if ev.button() == Qt.MouseButton.LeftButton:
            ev.accept()
            self.undo_zoom(reset=ev.modifiers() == Qt.KeyboardModifier.ShiftModifier)
            return

        super().mouseDoubleClickEvent(ev)

    # Zoom History -------------------------------------------------------------
    def undo_zoom(self, reset: bool = False):
        """ Go back in zoom history. """
        if self.axHistoryPointer == 0:
            self.enableAutoRange()
            self.axHistoryPointer = -1
            self.save_view()
            return

        if reset:
            # Go back to the first zoom
            self.scaleHistory(-len(self.axHistory))
            return

        # go one step back
        self.scaleHistory(-1)

    def save_view(self):
        """ Save the current view to the zoom history. """
        self.axHistoryPointer += 1
        self.axHistory = self.axHistory[:self.axHistoryPointer] + [self.viewRect()]

    # Auto Zoom ----------------------------------------------------------------
    def auto_zoom(self):
        """ Zoom to 6, 4 and 2 standard deviations and save the steps. """
        for nsigma in (6, 4, 2):
            self.set_y_range_to_n_sigma(nsigma)
            self.save_view()

    def set_y_range_to_n_sigma(self, n_sigma):
        """ Set the y-range to a number of standard deviations,
        assuming the data is taken from a normal distribution. """
        # Get the data from all curves in the viewbox
        all_data = []
        for item in self.allChildren():
            if isinstance(item, pg.PlotDataItem):
                y_data = item.yData
                if y_data is not None:
                    all_data.extend(y_data)

        if not all_data:
            return

        all_data = np.array(all_data)
        mean = np.mean(all_data)
        std_dev = np.std(all_data)

        y_min = mean - n_sigma * std_dev
        y_max = mean + n_sigma * std_dev

        self.setYRange(y_min, y_max, padding=0)
