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

        self.setStyleSheet(
            f":enabled {{ background-color: {colors.GREEN_DARK}; color: {colors.TEXT_LIGHT}; }}"
            f":disabled {{ background-color: {colors.GREEN_DARK_GREY}; color: {colors.GREYED_OUT_TEXT_DARK}; }}"
        )


class OpenButton(QtWidgets.QPushButton):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not args and not "text" in kwargs:
            self.setText("Open")

        self.setStyleSheet(
            f":enabled {{ background-color: {colors.GREEN_LIGHT}; color: {colors.TEXT_DARK}; }}"
            f":disabled {{ background-color: {colors.GREEN_LIGHT_GREY}; color: {colors.GREYED_OUT_TEXT_DARK}; }}"
            )


class RemoveButton(QtWidgets.QPushButton):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not args and not "text" in kwargs:
            self.setText("Remove")

        self.setStyleSheet(
            f":enabled {{ background-color: {colors.RED_DARK}; color: {colors.TEXT_LIGHT}; }}"
            f":disabled {{ background-color: {colors.RED_GREY}; color: {colors.GREYED_OUT_TEXT_DARK}; }}"
            )

class EditButton(QtWidgets.QPushButton):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not args and not "text" in kwargs:
            self.setText("Edit")

        self.setStyleSheet(
            f":enabled {{ background-color: {colors.BLUE_DARK}; color: {colors.TEXT_LIGHT}; }}"
            f":disabled {{ background-color: {colors.BLUE_GREY}; color: {colors.GREYED_OUT_TEXT_DARK}; }}"
            )

class DefaultButton(QtWidgets.QPushButton):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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

