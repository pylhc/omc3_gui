""" 
TFS Plotter
-----------

This module contains functions to plot TFS dataframes with pyqtgraph.
"""
from collections.abc import Sequence

import pandas as pd
import pyqtgraph as pg
from tfs.collection import TfsCollection


def plot_dataframes(plot: pg.PlotWidget, dataframes: Sequence[pd.DataFrame], xcolumn: str, ycolumn: str, yerrcolumn: str):
    data = pg.PlotDataItem([1,2,3], [4,5,6], data=["one", "two", "three"], name="Testing Line", symbol='o')
    data.scatter.opts['hoverable'] = True
    data.sigPointsHovered.connect(hovered)
    data.sigPointsClicked.connect(clicked)
    plot.addItem(data)
    # for df in dataframes:
    #     plot.plot(x=df[xcolumn], y=df[ycolumn], pen=None, symbol='o', symbolPen=None, symbolBrush='r', symbolSize=2)



def hovered(self, item, points):
    print('hovered')

def clicked(self, item, points):
    print('clicked')
