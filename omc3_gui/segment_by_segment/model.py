import enum
import types
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Sequence, Union

import pyqtgraph as pg
from accwidgets.graph import StaticPlotWidget
from omc3.segment_by_segment.segments import Segment
from qtpy import QtCore, QtWidgets
from qtpy.QtCore import QModelIndex, Qt

from omc3_gui.segment_by_segment.measurement_model import OpticsMeasurement


@dataclass
class Settings:
    pass


class ItemDictModel:
    """ Mixin-Class for a class that has a dictionary of items. """

    def __init__(self):
        self.items = {}

    def try_emit(self, emit: bool = True):
        if not emit:
            return

        if hasattr(self, "dataChanged"):
            # TODO: return which data has actually changed?
            self.dataChanged.emit(self.index(0), self.index(len(self.items)-1), [Qt.EditRole])
    
    def update_item(self, item):
        self.items[str(item)] = item
        self.try_emit()
    
    def add_item(self, item, emit: bool = True):
        name = str(item)
        if name in self.items.keys():
            raise ValueError(f"Item {name} already exists")
        self.items[name] = item
        self.try_emit(emit)

    def add_items(self, items: Sequence):
        for item in items:
            self.add_item(item, emit=False)
        self.try_emit()

    def remove_item(self, item, emit: bool = True):
        self.items.pop(str(item))
        self.try_emit(emit)
    
    def remove_items(self, items: Sequence):
        for item in items:
            self.remove_item(item, emit=False)
        self.try_emit()
    
    def remove_all_items(self):
        self.items = {}
        self.try_emit()

    def remove_item_at(self, index: int):
        self.remove_item(self.get_item_at(index))

    def remove_items_at(self, indices: Sequence):
        self.remove_items([self.get_item_at(index) for index in indices])

    def get_item_at(self, index: int) -> Any:
        return list(self.items.values())[index]


class MeasurementListModel(QtCore.QAbstractListModel, ItemDictModel):

    items: Dict[str, OpticsMeasurement]  # for the IDE
    
    class ColorIDs(enum.IntEnum):
        NONE = 0
        BEAM1 = enum.auto()
        BEAM2 = enum.auto()
        RING1 = enum.auto()
        RING2 = enum.auto()
        RING3 = enum.auto()
        RING4 = enum.auto()

        @classmethod
        def get_color(cls, meas: OpticsMeasurement) -> int:
            if meas.accel == "lhc":
                return getattr(cls, f"BEAM{meas.beam}")
            
            if meas.accel == "psb":
                return getattr(cls, f"RING{meas.ring}")
            
            return cls.NONE

    def __init__(self, *args, **kwargs):
        super(QtCore.QAbstractListModel, self).__init__(*args, **kwargs)
        super(ItemDictModel, self).__init__()

    def data(self, index: QtCore.QModelIndex, role: int = Qt.DisplayRole):

        meas: OpticsMeasurement = self.get_item_at(index.row())
        if role == Qt.DisplayRole:  # https://doc.qt.io/qt-5/qt.html#ItemDataRole-enum
            return meas.display()

        if role == Qt.ToolTipRole:
            return meas.tooltip()

        if role == Qt.TextColorRole:
            return self.ColorIDs.get_color(meas)

        if role == Qt.EditRole:
            return meas

    def rowCount(self, index: QtCore.QModelIndex = None):
        return len(self.items)


class SegmentTableModel(QtCore.QAbstractTableModel, ItemDictModel):

    _COLUMNS = {0: "Segment", 1: "Start", 2: "End"}
    _COLUMNS_MAP = {0: "name", 1: "start", 2: "end"}
    
    items: Dict[str, Segment]
    
    def __init__(self, *args, **kwargs): 
        super().__init__(*args, **kwargs)
        super(QtCore.QAbstractTableModel, self).__init__(*args, **kwargs)
        super(ItemDictModel, self).__init__()

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self._COLUMNS[section]
        return super().headerData(section, orientation, role)

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.items) 

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self._COLUMNS) 

    def data(self, index: QtCore.QModelIndex, role=QtCore.Qt.DisplayRole):
        i = index.row()
        j = index.column()
        segment: Segment = self.get_item_at(i)
        
        if role == QtCore.Qt.DisplayRole:
            return str(getattr(segment, self._COLUMNS_MAP[j]))
        
        if role == Qt.EditRole:
            return segment 
        
    def flags(self, index):
        return QtCore.Qt.ItemIsEnabled
