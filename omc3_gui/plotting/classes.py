""" 
Plotting: Classes
-----------------

Containers for figures, plots, etc.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
import numpy as np
import pyqtgraph as pg
from accwidgets.graph import StaticPlotWidget
from accwidgets.graph.widgets.plotitem import ExViewBox
from accwidgets.graph.widgets.plotwidget import GridOrientationOptions
from qtpy.QtCore import Signal, Qt, QRectF, QEvent

if TYPE_CHECKING:
    from qtpy.QtWidgets import QGraphicsSceneMouseEvent



class ObservablePlotDataItem(pg.PlotDataItem):
    """A PlotDataItem that emits a signal when visibility changes."""
    visibilityChanged = Signal(bool)

    def setVisible(self, visible):
        super().setVisible(visible)
        self.visibilityChanged.emit(visible)


class DualPlotWidget(pg.LayoutWidget):
    
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        pg.setConfigOptions(antialias=True)  # not sure if best place here

        self.top = PlotWidget()
        self.bottom = PlotWidget()

        self.addWidget(self.top, row=0, col=0)
        self.addWidget(self.bottom, row=1, col=0)

        # self.top.setMouseMode(pg.ViewBox.RectMode)
        # self.bottom.setMouseMode(pg.ViewBox.PanMode)

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
    
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, viewBox=ZoomingViewBox())  # requires accwidgets >= 3.0.11
        self.setBackground("w")
        self._set_show_grid(GridOrientationOptions.Both)


class ZoomingViewBox(ExViewBox):
    """ ViewBox that imitates the bahavior of the Java-GUI a bit closer. """
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setMouseMode(ZoomingViewBox.RectMode)  # mode that makes zooming rectangles
        self._zoom_history: list[QRectF] = []

    def suggestPadding(self, axis):
        if axis == 0:
            return 0.0  # disable padding for x axis
        return super().suggestPadding(axis)

    def set_y_range_to_n_sigma(self, n_sigma):
        """ Set the y-range to a number of standard deviations of the containing data. """
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

    def mouseClickEvent(self, ev: QGraphicsSceneMouseEvent):
        if ev.button() == Qt.MouseButton.MiddleButton:
            self._zoom_history.append(self.viewRect())
            for nsigma in (6, 4, 2):
                self.set_y_range_to_n_sigma(nsigma)
                self._zoom_history.append(self.viewRect())
            ev.accept()
            return 
        
        super().mouseClickEvent(ev)
        
    def mouseDoubleClickEvent(self, ev: QGraphicsSceneMouseEvent):
        if ev.button() == Qt.MouseButton.LeftButton:
            # Undo zoom history ---
            if not len(self._zoom_history):
                self.autoRange()
                self._zoom_history.append(self.viewRect())
                ev.accept()
                return  

            if ev.modifiers() == Qt.KeyboardModifier.ShiftModifier:  
                # go all the way back to the start
                self.setRange(self._zoom_history[0])
                self._zoom_history = []
            else:
                # go one step back
                self.setRange(self._zoom_history.pop())
            ev.accept()
            return 

        super().mouseDoubleClickEvent(ev)
        


