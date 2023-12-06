"""
Widgets 
-------

Pre-Defined Widgets go here.
"""

import math
from qtpy import QtWidgets, QtCore, QtGui
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

# Animations -------------------------------------------------------------------

class RunningSpinner(QtWidgets.QWidget):

    def __init__(self, center_on_parent=True, *args, **kwargs):
        self._spinner_color: QtGui.QColor = kwargs.pop("color", QtGui.QColor(colors.BLUE_DARK))
        self._spinner_roundness: float = kwargs.pop("roundness", 300.0)
        self._spinner_min_trail_opacity: float = kwargs.pop("min_trail_opacity", 0.05)
        self._spinner_trail_fade_percentage: float = kwargs.pop("trail_fade_percentage", 100.0)
        self._spinner_revolutions_per_second: float = kwargs.pop("revolutions_per_second", 1.2)
        self._spinner_n_lines: int = kwargs.pop("n_lines", 10)
        self._spinner_length: float = kwargs.pop("length", 5)
        self._spinner_radius: float = kwargs.pop("radius", 3)
        self._spinner_rotate: float = kwargs.pop("rotate", False)
        self._spinner_width: float = self._spinner_radius * 2 * math.pi / self._spinner_n_lines
        self._spinner_center: bool = center_on_parent

        self._angle: int = 0
        self._is_spinning: bool = False

        QtWidgets.QWidget.__init__(self, *args, **kwargs)
        
        self._animation = QtCore.QPropertyAnimation(self, b"angle", self)
        self._animation.setStartValue(0)
        self._animation.setEndValue(360)
        self._animation.setLoopCount(-1)
        self._animation.setDuration(int(1000 / self._spinner_revolutions_per_second))

        self.updateSize()

    @QtCore.Property(int)
    def angle(self):
        return self._angle

    @angle.setter
    def angle(self, value):
        self._angle = value % 360
        self.update()

    def updateSize(self):
        size = (self._spinner_radius + self._spinner_length) * 2
        self.setFixedSize(size, size)

    def updatePosition(self):
        parent = self.parentWidget()
        if parent and self._spinner_center:
            self.move(int(parent.width() / 2 - self.width() / 2),
                      int(parent.height() / 2 - self.height() / 2))

    def currentLineColor(self, line_number):
        color = QtGui.QColor(self._spinner_color)
        if line_number == 0:
            return color

        distance_threshold = math.ceil((self._spinner_n_lines - 1) * self._spinner_trail_fade_percentage / 100.0)
        if line_number > distance_threshold:
            color.setAlphaF(self._spinner_min_trail_opacity)

        else:
            alpha_diff = 1 - self._spinner_min_trail_opacity
            gradient = alpha_diff / distance_threshold
            alpha = color.alphaF() - gradient * line_number 
            alpha = min(1.0, max(0.0, alpha))
            color.setAlphaF(alpha)
        return color

    def paintEvent(self, event):
        self.updatePosition()
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtCore.Qt.transparent)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setPen(QtCore.Qt.NoPen)

        for idx_line in range(self._spinner_n_lines):
            painter.save()
            painter.translate(self._spinner_radius + self._spinner_length,
                              self._spinner_radius + self._spinner_length)
            rotateAngle = -(360.0 * idx_line / self._spinner_n_lines) + (self.angle if self._spinner_rotate else 0)
            color_index = idx_line + (int(self.angle / 360.0 * self._spinner_n_lines) if not self._spinner_rotate else 0)
            painter.rotate(rotateAngle)
            painter.translate(self._spinner_radius, 0)
            color = self.currentLineColor(color_index % self._spinner_n_lines)
            painter.setBrush(color)
            
            painter.drawRoundedRect(
                QtCore.QRect(int(0), -int(self._spinner_width / 2), int(self._spinner_length), int(self._spinner_width)),
                int(self._spinner_roundness),
                int(self._spinner_roundness), 
                QtCore.Qt.RelativeSize
            )
            painter.restore()

    def start(self):
        self.updatePosition()
        self._is_spinning = True
        self.show()
        self._animation.start()

    def stop(self):
        self._animation.stop()
        self._is_spinning = False
        self.hide()

    @property
    def is_spinning(self):
        return self._is_spinning
