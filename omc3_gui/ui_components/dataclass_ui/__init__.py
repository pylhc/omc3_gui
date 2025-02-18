""" 
DataClass UI
------------

A simple UI for dataclasses, which allows to edit the values of dataclasses
by the user within a dialog.
"""
from omc3_gui.ui_components.dataclass_ui import controller, view, model

# Dialogs ---
DataClassDialog = view.DataClassDialog
SettingsDialog = view.SettingsDialog

# Controller ---
DataClassUI = controller.DataClassUI
DataClassTabbedUI = controller.DataClassTabbedUI

# Model ---
FieldUIDef = model.FieldUIDef
DirectoryPath = model.DirectoryPath
FilePath = model.FilePath

metafield = model.metafield
choices_validator = model.choices_validator