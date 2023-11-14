"""
Widgets 
-------

Pre-Defined Widgets go here.
"""

from qtpy import QtWidgets


# Buttons ----------------------------------------------------------------------

class RunButton(QtWidgets.QPushButton):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not args and not "text" in kwargs:
            self.setText("Run")

        self.setStyleSheet("background-color: #28642A; color: #fff;")


class OpenButton(QtWidgets.QPushButton):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not args and not "text" in kwargs:
            self.setText("Open")

        self.setStyleSheet("background-color: #4CAF50; color: #000000;")


class RemoveButton(QtWidgets.QPushButton):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not args and not "text" in kwargs:
            self.setText("Remove")

        self.setStyleSheet("background-color: #f44336; color: #000000;")


class EditButton(QtWidgets.QPushButton):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not args and not "text" in kwargs:
            self.setText("Edit")

        self.setStyleSheet("background-color: #2196F3; color: #fff;")