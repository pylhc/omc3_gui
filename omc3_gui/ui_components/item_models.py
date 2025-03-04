""" 
UI: Item Models
---------------

Classes that makes it easier to handle unique items in UI models.
"""
from __future__ import annotations

from typing import Any, Protocol
from collections.abc import Hashable, Sequence

from qtpy import QtCore
from qtpy.QtCore import Qt


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
        self._items: list[Item] = []

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
        self._items = []
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
