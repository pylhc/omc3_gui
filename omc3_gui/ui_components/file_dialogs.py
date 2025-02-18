"""
UI: File Dialogs
----------------

Helper functions to open files.
"""
import logging
from pathlib import Path

from qtpy.QtWidgets import QApplication, QFileDialog, QStyle

LOGGER = logging.getLogger(__name__)


# Open Dialog Windows ----------------------------------------------------------
class OpenFilesDialog(QFileDialog):
    """ Quick dialog to open any kind of file. 
    Modifies QFileDialog, and allows only kwargs to be passed. 
    """
    
    def __init__(self, **kwargs) -> None:
        if "directory" in kwargs and isinstance(kwargs["directory"], Path): 
            kwargs["directory"] = str(kwargs["directory"])  # allow giving Paths

        super().__init__(**kwargs)  # parent, caption, directory, filter, options
        self.setOption(QFileDialog.Option.DontUseNativeDialog, True)

    def run_selection_dialog(self) -> list[Path]:
      if self.exec_():
         return [Path(f) for f in self.selectedFiles()]
      return []


class OpenFileDialog(OpenFilesDialog):
    """ Open a single file. """

    def __init__(self, caption: str = "Select File", **kwargs) -> None:
        super().__init__(caption=caption, **kwargs)  # parent, directory, filter, options
        self.setFileMode(QFileDialog.FileMode.ExistingFile)
    
    def run_selection_dialog(self) -> Path:
        selected = super().run_selection_dialog()
        if selected:
            return selected[0]
        return None


class OpenDirectoriesDialog(OpenFilesDialog):
    """ Open multiple directories. """

    def __init__(self, caption: str = "Select Folders", **kwargs) -> None:
        super().__init__(caption=caption, **kwargs)  # parent, directory, filter, options
        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        self.setWindowIcon(icon)
        self.setOption(QFileDialog.Option.ShowDirsOnly, True)
        self.setFileMode(QFileDialog.FileMode.ExistingFiles) 

    def accept(self):
        """This function is called when the user clicks on "Open".
        Normally, when selecting a directories, the first directory is followed/opened inside the dialog, 
        i.e. its content is shown. Overwrite super().accept() to prevent that and close the dialog instead.
        """
        for selected in self.selectedFiles():
            if not Path(selected).is_dir():  # this should not happen, as only directories are shown
                LOGGER.warning(f"{selected} is not a directory. Try again.")
                return

        self.done(QFileDialog.Accepted)


class OpenDirectoryDialog(OpenDirectoriesDialog):
    """ Open a single directory. """

    def __init__(self, caption: str = "Select Folder", **kwargs) -> None:
        super().__init__(caption=caption, **kwargs)  # parent, directory, filter, options
        self.setFileMode(QFileDialog.FileMode.Directory)
    
    def run_selection_dialog(self) -> Path:
        selected = super().run_selection_dialog()
        if selected:
            return selected[0]
        return None


class OpenAnyMultiDialog(OpenFilesDialog):
    """ Open multiple files/folders. """

    def __init__(self, caption: str = "Select Files", existing: bool = True, **kwargs) -> None:
        super().__init__(caption=caption, **kwargs)  # parent, directory, filter, options
        if existing:
            self.setFileMode(QFileDialog.FileMode.ExistingFiles)
    
    def accept(self):
        """This function is called when the user clicks on "Open".
        Normally, when selecting a directories, the first directory is followed/opened inside the dialog, 
        i.e. its content is shown. 
        Overwrite super().accept() to prevent that and close the dialog instead.
        """
        if not self.selectedFiles():
            LOGGER.warning("Nothing selected. Try again or cancel.")
            return

        self.done(QFileDialog.Accepted)
    

class OpenAnySingleDialog(OpenAnyMultiDialog):
    """ Open a single file/folder. """

    def __init__(self, caption: str = "Select Single", **kwargs) -> None:
        existing = kwargs.get("existing", True)
        super().__init__(caption=caption, **kwargs)  # parent, directory, filter, options
        if existing:
            self.setFileMode(QFileDialog.FileMode.ExistingFile)
    
    def run_selection_dialog(self) -> Path:
        selected = super().run_selection_dialog()
        if selected:
            return selected[0]
        return None
