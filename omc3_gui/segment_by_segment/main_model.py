import enum
from dataclasses import dataclass
import logging
from typing import Any, Dict, Hashable, List, Protocol, Sequence

from qtpy import QtCore
from qtpy.QtCore import Qt


from omc3_gui.segment_by_segment.measurement_model import OpticsMeasurement
from omc3_gui.segment_by_segment.segment_model import SegmentModel

LOGGER = logging.getLogger(__name__)


@dataclass
class Settings:
    pass


class Item(Protocol):
    """ Protocol for a class that has an 'id'-property. 
    As used in :class:`omc3_gui.segment_by_segment.main_model.UniqueItemListModel`,
    this id defines whether two items are "the same", i.e. only one of them 
    can be present in the model.
    Example: For the Segments, this should be the name, as if we have two segements
    with the same name, running them overwrites each other.
    """
    id: Hashable


class UniqueItemListModel:
    """ Mixin-Class for a class that has a dictionary of items. 
    Note: I have considered using QAbstractItemModel/QStandardItemModel, 
    but I do not need all the features it provides, so this should be easier
    and allows for keeping items unique (jdilly, 2023).
    All items need to have an 'id'-property.
    """

    def __init__(self):
        self._items: List[Item] = []

    def try_emit_change(self, emit: bool = True):
        """ Emits a dataChanged-signal if the model has changed, and if the 
        class provides such a signal. """
        if not emit:
            return

        if hasattr(self, "dataChanged"):
            # TODO: return which data has actually changed?
            try:
                idx_start = self.index(0)  # list
                idx_end = self.index(self.rowCount()-1)
            except TypeError:
                idx_start = self.index(0, 0)  # table
                idx_end = self.index(self.rowCount()-1, self.columnCount()-1)
                self.headerDataChanged.emit(Qt.Horizontal, 0, self.columnCount()-1)
            self.dataChanged.emit(idx_start, idx_end)
    
    def add_item(self, item: Item, emit: bool = True):
        """ Adds an item to the model, 
        if an item with the same id is not already present. """
        if item.id in [i.id for i in self._items]:
            raise ValueError(f"Item {item.id} already exists")
        self._items.append(item)
        self.try_emit_change(emit)

    def add_items(self, items: Sequence[Item]):
        """ Adds all items from a list to the model, 
        for which items with the same id are not already present. """
        already_exist_items = []
        for item in items:
            try:
                self.add_item(item, emit=False)
            except ValueError:
                already_exist_items.append(item)
        self.try_emit_change()
        if already_exist_items:
            raise ValueError(f"Items already exist: {already_exist_items}")

    def remove_item(self, item: Item, emit: bool = True):
        """ Removes an item from the model. """
        self._items.remove(item)
        self.try_emit_change(emit)
    
    def remove_items(self, items: Sequence[Item]):
        """ Removes all items from a list from the model, if they exist. """
        do_not_exist_items = []
        for item in items:
            try:
                self.remove_item(item, emit=False)
            except ValueError:
                do_not_exist_items.append(item)
        self.try_emit_change()
        if do_not_exist_items:
            raise ValueError(f"Items do not exist: {do_not_exist_items}")
    
    def clear(self):
        """ Removes all items from the model. """
        self.items = []
        self.try_emit_change()

    def remove_item_at(self, index: int):
        self.remove_item(self.get_item_at(index))

    def remove_items_at(self, indices: Sequence):
        self.remove_items([self.get_item_at(index) for index in indices])

    def get_item_at(self, index: int) -> Any:
        return self._items[index]

    def get_index(self, item: Item) -> QtCore.QModelIndex:
        idx_item = self._items.index(item)
        try:
            return self.index(idx_item)
        except TypeError:
            return self.index(idx_item, 0)


class MeasurementListModel(QtCore.QAbstractListModel, UniqueItemListModel):

    _items: Dict[str, OpticsMeasurement]  # only for the IDE
    
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
        super(UniqueItemListModel, self).__init__()

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
        return len(self._items)


class SegmentTableModel(QtCore.QAbstractTableModel, UniqueItemListModel):

    _COLUMNS = {0: "Segment", 1: "Start", 2: "End"}
    _COLUMNS_MAP = {0: "name", 1: "start", 2: "end"}
    
    _items: Dict[str, SegmentModel]  # only for the IDE
    
    def __init__(self, *args, **kwargs): 
        super(QtCore.QAbstractTableModel, self).__init__(*args, **kwargs)
        super(UniqueItemListModel, self).__init__()

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self._COLUMNS[section]
        return super().headerData(section, orientation, role)

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self._items) 

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
                self.update_item(segment, old_id=old_name)
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
