import enum
from dataclasses import dataclass
import logging
from typing import Any, Dict, Sequence

from qtpy import QtCore
from qtpy.QtCore import Qt


from omc3_gui.segment_by_segment.measurement_model import OpticsMeasurement
from omc3_gui.segment_by_segment.segment_model import SegmentModel

LOGGER = logging.getLogger(__name__)


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
            try:
                idx_start = self.index(0)  # list
                idx_end = self.index(len(self.items)-1)
            except TypeError:
                idx_start = self.index(0, 0)  # table
                idx_end = self.index(self.rowCount()-1, self.columnCount()-1)
                self.headerDataChanged.emit(Qt.Horizontal, 0, self.columnCount()-1)
            self.dataChanged.emit(idx_start, idx_end)
    
    def update_item(self, item, old_name: str = None):
        if old_name is not None:
            self.items.pop(old_name)
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

    def get_index(self, item: Any) -> QtCore.QModelIndex:
        idx_item = list(self.items.keys()).index(str(item))
        try:
            return self.index(idx_item)
        except TypeError:
            return self.index(idx_item, 0)


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
        # https://doc.qt.io/qt-5/qt.html#ItemDataRole-enum
        if role == Qt.DisplayRole:  
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
    
    items: Dict[str, SegmentModel]
    
    def __init__(self, *args, **kwargs): 
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
        segment: SegmentModel = self.get_item_at(i)
        
        if role == QtCore.Qt.DisplayRole:
            return str(getattr(segment, self._COLUMNS_MAP[j]))
        
        if role == Qt.EditRole:
            return segment

    def setData(self, index, value, role):
        i = index.row()
        j = index.column()
        segment: SegmentModel = self.get_item_at(i)
        old_name = segment.name 

        if role == Qt.EditRole:
            if value is None or value == "":
                return False

            setattr(segment, self._COLUMNS_MAP[j], value)
            if segment.name != old_name:
                self.update_item(segment, old_name=old_name)
            else:
                self.dataChanged.emit(index, index)
            return True
    
    def toggle_row(self, index):
        i = index.row()
        segment: SegmentModel = self.get_item_at(i)
        segment.enabled = not segment.enabled
        self.headerDataChanged.emit(Qt.Horizontal, 0, self.rowCount() - 1)
        self.dataChanged.emit(self.index(i, 0), self.index(i, self.rowCount() - 1))
        
    def flags(self, index):
        i = index.row()
        j = index.column()
        segment: SegmentModel = self.get_item_at(i)
        if segment.enabled:
            return Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsSelectable

        return Qt.ItemIsEditable | Qt.ItemIsSelectable
