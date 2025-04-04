""" 
Main Model
----------

This is the main model for the Segment-by-Segment application.
"""
from __future__ import annotations

import enum
import logging

from qtpy import QtCore
from qtpy.QtCore import Qt

from omc3_gui.segment_by_segment.measurement_model import OpticsMeasurement
from omc3_gui.segment_by_segment.segment_model import SegmentItemModel
from omc3_gui.ui_components.item_models import UniqueItemListModel

ItemDataRole = Qt.ItemDataRole
ItemFlag = Qt.ItemFlag

LOGGER = logging.getLogger(__name__)

class MeasurementListModel(QtCore.QAbstractListModel, UniqueItemListModel):

    _items: list[OpticsMeasurement]  # only for the IDE
    
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

    def data(self, index: QtCore.QModelIndex, role: int = ItemDataRole.DisplayRole):

        meas: OpticsMeasurement = self.get_item_at(index.row())
        # https://doc.qt.io/qt-5/qt.html#ItemDataRole-enum
        if role == ItemDataRole.DisplayRole:  
            return meas.display()

        if role == ItemDataRole.ToolTipRole:
            return meas.tooltip()

        if role == Qt.TextColorRole:
            return self.ColorIDs.get_color(meas)

        if role == ItemDataRole.UserRole:
            return meas

    def rowCount(self, index: QtCore.QModelIndex = None):
        return len(self._items)

    @property
    def items(self):
        return self._items


class SegmentTableModel(QtCore.QAbstractTableModel, UniqueItemListModel):
    """ Data Model for the table of segments. 
    
    Hint: Uses Qt.UserRole to retrieve the actual segment.
    """

    _COLUMNS: list[str] = ["Segment", "Start", "End"]  # display names
    _ATTRIBUTES: list[str] = ["name", "start", "end"]  # segment attributes
    
    _items: list[SegmentItemModel]  # only for the IDE
    
    def __init__(self, *args, **kwargs): 
        super(QtCore.QAbstractTableModel, self).__init__(*args, **kwargs)
        super(UniqueItemListModel, self).__init__()  # Items need to be unique

    def headerData(self, section, orientation, role=ItemDataRole.DisplayRole):
        """ Sets the header of the table. """
        # When we are displaying the header, use the display column names
        if orientation == QtCore.Qt.Horizontal and role == ItemDataRole.DisplayRole:
            return self._COLUMNS[section]

        # Otherwise whatever the default is    
        return super().headerData(section, orientation, role)

    def rowCount(self, parent=QtCore.QModelIndex()):
        """ Returns the number of rows in the model. """
        return len(self._items) 

    def columnCount(self, parent=QtCore.QModelIndex()):
        """ Returns the number of columns in the model. """
        return len(self._COLUMNS) 

    def data(self, index: QtCore.QModelIndex, role=ItemDataRole.DisplayRole):
        """ Return the data, depending on index and role. """
        i = index.row()
        j = index.column()
        segment: SegmentItemModel = self.get_item_at(i)
        
        if role == ItemDataRole.DisplayRole or role == ItemDataRole.EditRole:
            return str(getattr(segment, self._ATTRIBUTES[j]))
        
        if role == ItemDataRole.ToolTipRole:
            return segment.tooltip()

        if role == ItemDataRole.UserRole:
            return segment
        
    def setData(self, index, value, role):
        """ Set the data, depending on index and role. """
        i = index.row()
        j = index.column()
        segment: SegmentItemModel = self.get_item_at(i)

        if role == ItemDataRole.EditRole:
            if value is None or value == "":
                return False
            
            attribute = self._ATTRIBUTES[j]
            setattr(segment, attribute, value)

            self.dataChanged.emit(index, index)
            return True
        
    def flags(self, index):
        """ Set the flags for the given index. 
        At the moment: all elements are editable and selectable. """
        return ItemFlag.ItemIsEnabled | ItemFlag.ItemIsEditable | ItemFlag.ItemIsSelectable
