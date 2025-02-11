""" 
Segment-by-Segment Model
------------------------

This is the main model for the Segment-by-Segment application.
"""
from __future__ import annotations

import enum
import logging

from qtpy import QtCore
from qtpy.QtCore import Qt

from omc3_gui.segment_by_segment.measurement_model import OpticsMeasurement
from omc3_gui.segment_by_segment.segment_model import SegmentItemModel
from omc3_gui.utils.widgets import showErrorDialog
from omc3_gui.utils.item_models import UniqueItemListModel

LOGGER = logging.getLogger(__name__)


class MeasurementListModel(QtCore.QAbstractListModel, UniqueItemListModel):

    _items: dict[str, OpticsMeasurement]  # only for the IDE
    
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

        if role == Qt.UserRole:
            return meas

    def rowCount(self, index: QtCore.QModelIndex = None):
        return len(self._items)


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

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        """ Sets the header of the table. """
        # When we are displaying the header, use the display column names
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self._COLUMNS[section]

        # Otherwise whatever the default is    
        return super().headerData(section, orientation, role)

    def rowCount(self, parent=QtCore.QModelIndex()):
        """ Returns the number of rows in the model. """
        return len(self._items) 

    def columnCount(self, parent=QtCore.QModelIndex()):
        """ Returns the number of columns in the model. """
        return len(self._COLUMNS) 

    def data(self, index: QtCore.QModelIndex, role=QtCore.Qt.DisplayRole):
        """ Return the data, depending on index and role. """
        i = index.row()
        j = index.column()
        segment: SegmentItemModel = self.get_item_at(i)
        
        if role == Qt.DisplayRole or role == Qt.EditRole:
            return str(getattr(segment, self._ATTRIBUTES[j]))
        
        if role == Qt.ToolTipRole:
            return segment.tooltip()

        if role == Qt.UserRole:
            return segment
        
    def setData(self, index, value, role):
        """ Set the data, depending on index and role. """
        i = index.row()
        j = index.column()
        segment: SegmentItemModel = self.get_item_at(i)

        if role == Qt.EditRole:
            if value is None or value == "":
                return False
            
            attribute = self._ATTRIBUTES[j]
            setattr(segment, attribute, value)

            self.dataChanged.emit(index, index)
            return True
        
    def flags(self, index):
        """ Set the flags for the given index. 
        At the moment: all elements are editable and selectable. """
        return Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsSelectable
