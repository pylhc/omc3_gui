
""" 
DataClass UI: View 
------------------

The frontend components that make up the dataclass UI,
in particular the dialog windows that can be used to edit dataclasses.
"""
from __future__ import annotations

import logging
from typing import Protocol

from qtpy import QtWidgets

from omc3_gui.ui_components.dataclass_ui import controller

LOGGER = logging.getLogger(__name__)
class DataClassInterface(Protocol):
    """ Protocol for the DataClassDialog. 
    Observed by :class:`omc3_gui.utils.dataclass_ui.controller.DataClassUI` and 
    :class:`omc3_gui.utils.dataclass_ui.controller.DataClassTabbedUI`, 
    both of which can hence be used with the dialog.
    """
    layout: QtWidgets.QLayout
    model: object

    def update_ui(self): ...
    def update_model(self): ...
    def validate(self, only_modified: bool = False): ...
    def reset_labels(self): ...


class DataClassDialog(QtWidgets.QDialog):
    """ Simple dialog window to display the DataClassUI layout. 
    Adds some convenience functionality like "Ok" and "Cancel" buttons
    and automatic data-validation on close.
    """
    WINDOW_TITLE = "Edit DataClass"
    DEFAULT_SIZE = (800, 600)  # width, height, use -1 for auto
    
    def __init__(self, dataclass_ui: DataClassInterface, parent = None):
        super().__init__(parent)
        self._button_box: QtWidgets.QDialogButtonBox = None
        
        self._dataclass_ui: DataClassInterface = dataclass_ui
        self._build_gui()
        self._connect_signals()
        self._set_size(width=self.DEFAULT_SIZE[0], height=self.DEFAULT_SIZE[1])
        self.update_ui()
        self.validate_only_modified: bool = True


    def _set_size(self, width: int = -1, height: int = -1):
        # Set position to the center of the parent (does not work in WSL for me, jdilly 2023)
        # parent = self.parent()
        # if parent is not None:
        #     parent_geo = parent.geometry()
        #     parent_pos = parent.mapToGlobal(parent.pos())  # multiscreen support
        #     if width >= 0:
        #         x = parent_pos.x() + parent_geo.width() / 2
        #     else:
        #         x = parent_pos.x() + (parent_geo.width() - width) / 2

        #     if height >=0 :
        #         y = parent_pos.y() + parent_geo.height() / 2
        #     else:
        #         y = parent_pos.y() + (parent_geo.height() - height) / 2
        #     self.move(x, y)
        
        # Set size
        self.resize(width, height)

    def _build_gui(self):
        self.setWindowTitle(self.WINDOW_TITLE)
        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(self._dataclass_ui.layout)

        QBtn = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        self._button_box = QtWidgets.QDialogButtonBox(QBtn)
        layout.addWidget(self._button_box)

        self.setLayout(layout)
    
    def _connect_signals(self):
        self._button_box.accepted.connect(self.accept)
        self._button_box.rejected.connect(self.reject)

    def update_ui(self, new_model: object = None):
        if new_model is not None:
            self._dataclass_ui.model = new_model 
        self._dataclass_ui.update_ui()  # triggers changes, so the labels appear in "changed" state
        self._dataclass_ui.reset_labels()  # so we reset them

    def accept(self):
        try:
            self._dataclass_ui.validate(only_modified=self.validate_only_modified)
        except ValueError as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return

        self._dataclass_ui.update_model()
        super().accept() 


class SettingsDialog(DataClassDialog):
    """ Slight modification of the DataClassDialog to be used for Tabbed-Settings. """

    WINDOW_TITLE = "Settings"
    DEFAULT_SIZE = (800, -1)
    
    def __init__(self, settings: object, parent=None):
        dataclass_tabbed_ui = controller.DataClassTabbedUI(dclass=settings)       
        super().__init__(dataclass_ui=dataclass_tabbed_ui, parent=parent)

    @property
    def settings(self) -> object:
        return self._dataclass_ui.model


# Type-to-Widget Helpers ----------------------------------------------------------------

class QFullIntSpinBox(QtWidgets.QSpinBox):
    """ Like a QSpinBox, but overwriting default range(0,100) with maximum integer range. """

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setRange(-2**31, 2**31 - 1)  # range of signed 32-bit integers 


