import sys
from typing import List, Union
from qtpy.QtCore import QObject
from qtpy.QtWidgets import QApplication, QFileDialog, QMenuBar, QDesktopWidget, QWidgetAction
from omc3_gui import __version__

try:
    from accwidgets.app_frame import ApplicationFrame
    from accwidgets.qt import exec_app_interruptable
except ImportError:
    from qtpy.QtWidgets import QMainWindow as ApplicationFrame
    exec_app_interruptable = lambda app: app.exec()



class Controller(QObject):

    def __init__(self, view: ApplicationFrame, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._view = view

    def show(self):
        self._view.show()

    @classmethod
    def run_application(cls, *args, **kwargs):
        app = QApplication(sys.argv)
        controller = cls(*args, **kwargs)
        controller.show()
        sys.exit(exec_app_interruptable(app))
    


class View(ApplicationFrame):

    __app_version__ = __version__
    _menu_bar: QMenuBar
    
    def __init__(self, *args, **kwargs):
        kwargs["use_log_console"] = kwargs.get("use_log_console", True)
        try:
            super().__init__(*args, **kwargs)  # CERN Application Frame
        except TypeError:
            del kwargs["use_log_console"]
            super().__init__(*args, **kwargs)   # QT Main window

        if getattr(self, "log_console"):
            self.log_console.console.expanded = False
            self.log_console.setFeatures(
                self.log_console.DockWidgetClosable | self.log_console.DockWidgetMovable
            )
        
        # Sizing ---
        screen_shape = QDesktopWidget().screenGeometry()
        self.resize(2 * screen_shape.width() / 3,
                    2 * screen_shape.height() / 3)

        self.build_menu_bar()

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


    def setWindowTitle(self, title: str):
        super().setWindowTitle(f"{title} v{self.__app_version__}")

    def toggleFullScreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()