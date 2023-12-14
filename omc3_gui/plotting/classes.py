

import pyqtgraph as pg
from accwidgets.graph import StaticPlotWidget
from accwidgets.graph.widgets.plotitem import ExViewBox

class DualPlot(pg.LayoutWidget):
    
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.top = PlotWidget()
        self.bottom = PlotWidget()

        self.addWidget(self.top, row=0, col=0)
        self.addWidget(self.bottom, row=1, col=0)

        # self.top.setMouseMode(pg.ViewBox.RectMode)
        # self.bottom.setMouseMode(pg.ViewBox.PanMode)

    @property
    def plots(self):
        return (self.top, self.bottom)
    

    def connect_x(self) -> None:
        pass

    def connect_y(self) -> None:
        pass


class PlotWidget(StaticPlotWidget):
    
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, viewBox=ZoomingViewBox())
        
        # fixes for our plots
        self.setBackground("w")
        self.plotItem.getViewBox().setMouseMode(ZoomingViewBox.RectMode)


class ZoomingViewBox(ExViewBox):
    pass

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
