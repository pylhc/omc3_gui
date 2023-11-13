from dataclasses import dataclass
from pathlib import Path
import types
from typing import Any, Dict, List, Sequence, Union
from accwidgets.graph import StaticPlotWidget
import pyqtgraph as pg
from omc3.segment_by_segment.segments import Segment

from typing import List
from qtpy import QtCore
from qtpy.QtCore import Qt


@dataclass
class Measurement:
    measurement_dir: Path
    output_dir: Path = None
    elements: Dict[str, Segment] = None
    segments: Dict[str, Segment] = None
    model_dir: Path = None
    accel: str = None
    year: str = None
    ring: int = None

    def __str__(self):
        return str(self.measurement_dir)
    


@dataclass
class Settings:
    pass



class ItemDictModel:

    def __init__(self):
        self.items = {}

    def try_emit(self, emit: bool = True):
        if not emit:
            return

        if hasattr(self, "layoutChanged"):
            self.layoutChanged.emit()
    
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

    items: Dict[str, Measurement]  # for the IDE

    def __init__(self, *args, **kwargs):
        super(QtCore.QAbstractListModel, self).__init__(*args, **kwargs)
        super(ItemDictModel, self).__init__()

    def data(self, index: QtCore.QModelIndex, role: int = Qt.DisplayRole):
        meas: Measurement = self.get_item_at(index.row())
        if role == Qt.DisplayRole:  # https://doc.qt.io/qt-5/qt.html#ItemDataRole-enum
            return str(meas)
        
        if role == Qt.EditRole:
            return meas

    def rowCount(self, index):
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

    def data(self, index, role=QtCore.Qt.DisplayRole):
        i = index.row()
        j = index.column()
        segment: Segment = self.get_item_at(i)
        
        if role == QtCore.Qt.DisplayRole:
            return str(getattr(segment, self._COLUMNS_MAP[j]))
        
        if role == Qt.EditRole:
            return segment 
        
    def flags(self, index):
        return QtCore.Qt.ItemIsEnabled
