import logging
import re
import sys
from typing import List, Union
import typing
from qtpy.QtCore import QObject, Slot, QEvent, Qt
from qtpy.QtWidgets import QApplication, QFileDialog, QMenuBar, QDesktopWidget, QWidgetAction, QStatusBar, QToolTip
from qtpy import QtGui
from omc3_gui import __version__
from omc3_gui.utils.log_handler import get_console_formatter
from omc3_gui.utils.widgets import RunningSpinner

try:
    from accwidgets.app_frame import ApplicationFrame
    from accwidgets.qt import exec_app_interruptable
except ImportError:
    from qtpy.QtWidgets import QMainWindow as ApplicationFrame
    exec_app_interruptable = lambda app: app.exec()

try:
    from accwidgets.log_console import LogConsoleFormatter as AccPyLogConsoleFormatter
    from accwidgets.app_frame._about_dialog import AboutDialog
except ImportError:
    AccPyLogConsoleFormatter = object
    AboutDialog = None



class Controller(QObject):

    def __init__(self, view: ApplicationFrame, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._view = view

    def show(self):
        self._view.show()

    @classmethod
    def run_application(cls, *args, **kwargs) -> int:
        app = QApplication(sys.argv)
        controller = cls(*args, **kwargs)
        controller.show()
        return exec_app_interruptable(app)
    

class View(ApplicationFrame):

    
    def __init__(self, *args, **kwargs):
        kwargs["use_log_console"] = kwargs.get("use_log_console", True)
        try:
            super().__init__(*args, **kwargs)  # CERN Application Frame
        except TypeError:
            del kwargs["use_log_console"]
            super().__init__(*args, **kwargs)   # QT Main window
        
        self._menu_bar: QMenuBar = None
        self._thread_spinner: RunningSpinner = None
        self.app_version = __version__

        self._adapt_logger()
        self._adapt_to_screensize()
        self.build_menu_bar()
        self.build_status_bar()

    def build_menu_bar(self):
        self._menu_bar = QMenuBar()
        
        # File menu ---
        file = self._menu_bar.addMenu("File")
        quit = file.addAction("Exit", self.close)
        quit.setMenuRole(QWidgetAction.QuitRole)

        # View menu ---
        view = self._menu_bar.addMenu("View")
        toggle_fullscreen = view.addAction("Full Screen", self.toggleFullScreen)
        toggle_fullscreen.setCheckable(True)

        # Help menu ---
        help = self._menu_bar.addMenu("Help")
        about = help.addAction("About", self.showAboutDialog)
        about.setMenuRole(QWidgetAction.AboutRole)

        # Set menu bar ---
        self.setMenuBar(self._menu_bar)

    def build_status_bar(self):
        status_bar: QStatusBar = self.statusBar()
        
        # Build thread spinner ---
        thread_spinner = RunningSpinner(parent=status_bar, center_on_parent=False)
        status_bar.addPermanentWidget(thread_spinner)
        thread_spinner.mouseDoubleClickEvent = lambda *args, **kwargs: self.sig_thread_spinner_double_clicked.emit()
        thread_spinner.stop()
        self._thread_spinner = thread_spinner
       
        self.setStatusBar(status_bar)
    
    @property
    def thread_spinner(self) -> RunningSpinner:
        return self._thread_spinner

    def _adapt_to_screensize(self):
        """ Sets the window size to 2/3 of the screen size. """
        screen_shape = QDesktopWidget().screenGeometry()
        self.resize(
            int(2 * screen_shape.width() / 3),
            int(2 * screen_shape.height() / 3)
        )

    def _adapt_logger(self):
        """ Changes the appearance of the log console. """
        if getattr(self, "log_console") is None:
            return
        self.log_console.console.expanded = False
        self.log_console.setFeatures(
            self.log_console.DockWidgetClosable | self.log_console.DockWidgetMovable
        )
        self.log_console.console.formatter = LogConsoleFormatter(show_date=False)  # see below
        self.log_console.console._set_color_to_scheme(color=QtGui.QColor("#b6b6b6b"), level=logging.DEBUG)  # default: black
        # self.log_console.console._set_color_to_scheme(color=QtGui.QColor("#000000"), level=logging.INFO)    # default: green
        self.log_console.console.model.buffer_size = 10_000  # default: 1000
        if sys.flags.debug:
            self.log_console.console.model.visible_levels |=  {logging.DEBUG}

    def setWindowTitle(self, title: str):
        super().setWindowTitle(f"{title} v{self.app_version}")

    def toggleFullScreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    @Slot()
    def showAboutDialog(self) -> None:
        """
        Display an 'about' dialog.
        """
        if AboutDialog is None:
            return

        name = self.windowTitle()
        try:
            name = " ".join(name.split()[:-1])
        except (IndexError, TypeError, AttributeError):
            pass

        dialog = AboutDialog(
            app_name=name,
            version=self.appVersion,
            icon=self.windowIcon(),
            parent=self,
        )
        dialog.exec_()


class LogConsoleFormatter(AccPyLogConsoleFormatter):

    def __init__(self, show_date: bool = True, show_time: bool = True, show_logger_name: bool = True) -> None:
        """
        Reimplementation of the AccPy LogConsoleFormatter, to allow for a different logging format.

        Args:
            show_date: Add date to the log message prefix.
            show_time: Add time to the log message prefix.
            show_logger_name: Add logger name to the log message prefix.
        """
        super().__init__()

        self.show_date = show_date
        self.show_time = show_time
        self.show_logger_name = show_logger_name

        fmt_str = get_console_formatter()._fmt
        date_format = []

        if show_date:
            date_format.append("%Y-%m-%d")
        if show_time:
            date_format.append("%H:%M:%S")
        
        if not show_date and not show_time:
            fmt_str = re.sub(r"\%\(asctime\)\d+s\s+", "", fmt_str)

        if not show_logger_name:
            fmt_str = re.sub(r"\%\(name\)\d+s\s+", "", fmt_str)
        
        fmt_str = fmt_str[fmt_str.index("%"):]

        self._fmt = logging.Formatter(fmt=fmt_str, datefmt=" ".join(date_format), style="%")
