""" 
Plotting: Classes
-----------------

Containers for figures, plots, etc.
"""
import pyqtgraph as pg
from accwidgets.graph import StaticPlotWidget
from accwidgets.graph.widgets.plotitem import ExViewBox
from accwidgets.graph.widgets.plotwidget import GridOrientationOptions
from qtpy.QtCore import Signal


class ObservablePlotDataItem(pg.PlotDataItem):
    """A PlotDataItem that emits a signal when visibility changes."""
    visibilityChanged = Signal(bool)

    def setVisible(self, visible):
        super().setVisible(visible)
        self.visibilityChanged.emit(visible)


class DualPlot(pg.LayoutWidget):
    
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
    """ ViewBox that imitates the bahavior of the Java-GUI a bit closer. 
    
    TODO: !
    """
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setMouseMode(ZoomingViewBox.RectMode)  # mode that makes zooming rectangles

    def suggestPadding(self, axis):
        if axis == 0:
            return 0.0  # disable padding for x axis
        return super().suggestPadding(axis)

    # def mouseDragEvent(self, ev):

    #     if ev.button() == QtCore.Qt.RightButton:
    #         ev.ignore()
    #     else:
    #         pg.ViewBox.mouseDragEvent(self, ev)

    #     ev.accept()
    #     pos = ev.pos()
    #     if ev.button() == QtCore.Qt.RightButton:
    #         if ev.isFinish():
    #             self.rbScaleBox.hide()
    #             self.ax = QtCore.QRectF(
    #                 pg.Point(ev.buttonDownPos(ev.button())), pg.Point(pos)
    #             )
    #             self.ax = self.childGroup.mapRectFromParent(self.ax)
    #             self.Coords = self.ax.getCoords()
    #             self.getdataInRect()
    #             self.changePointsColors()
    #         else:
    #             self.updateScaleBox(ev.buttonDownPos(), ev.pos())


