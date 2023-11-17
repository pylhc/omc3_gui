"""
Widgets 
-------

Pre-Defined Widgets go here.
"""

from qtpy import QtWidgets
from omc3_gui.utils import colors

# Buttons ----------------------------------------------------------------------

class RunButton(QtWidgets.QPushButton):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not args and not "text" in kwargs:
            self.setText("Run")

        self.setStyleSheet(f"background-color: {colors.GREEN_DARK}; color: {colors.TEXT_LIGHT};")


class OpenButton(QtWidgets.QPushButton):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not args and not "text" in kwargs:
            self.setText("Open")

        self.setStyleSheet(f"background-color: {colors.GREEN_LIGHT}; color: {colors.TEXT_DARK};")


class RemoveButton(QtWidgets.QPushButton):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not args and not "text" in kwargs:
            self.setText("Remove")
        
        self.setStyleSheet(f"background-color: {colors.RED_LIGHT}; color: {colors.TEXT_DARK};")



class EditButton(QtWidgets.QPushButton):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not args and not "text" in kwargs:
            self.setText("Edit")

        self.setStyleSheet(f"background-color: {colors.BLUE_DARK}; color: {colors.TEXT_LIGHT};")


# Filler -----------------------------------------------------------------------

class HorizontalSeparator(QtWidgets.QFrame):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFrameShape(QtWidgets.QFrame.HLine)
        self.setFrameShadow(QtWidgets.QFrame.Sunken) 


class VerticalSeparator(QtWidgets.QFrame):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFrameShape(QtWidgets.QFrame.VLine)
        self.setFrameShadow(QtWidgets.QFrame.Sunken)

