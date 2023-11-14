
import logging
from pathlib import Path
from typing import List, Optional, Union

from qtpy.QtWidgets import QApplication, QFileDialog, QStyle

LOGGER = logging.getLogger(__name__)


# Open Dialog Windows ----------------------------------------------------------
class OpenAnyFileDialog(QFileDialog):
    
    def __init__(self, **kwargs) -> None:
        """ Quick dialog to open any kind of file. 
        Modifies QFileDialog, and allows only kwargs to be passed. 
        """
        super().__init__(**kwargs)  # parent, caption, directory, filter, options
        self.setOption(QFileDialog.Option.DontUseNativeDialog, True)

    def run_selection_dialog(self) -> List[Path]:
      if self.exec_():
         return [Path(f) for f in self.selectedFiles()]
      return []


class OpenDirectoriesDialog(OpenAnyFileDialog):
    def __init__(self, caption = "Select Folders", **kwargs) -> None:
        super().__init__(caption=caption, **kwargs)  # parent, directory, filter, options
        icon = QApplication.style().standardIcon(QStyle.SP_DirIcon)
        self.setWindowIcon(icon)
        self.setOption(QFileDialog.Option.ShowDirsOnly, True)
        self.setFileMode(QFileDialog.ExistingFiles) 

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
    def __init__(self, caption = "Select Folder", **kwargs) -> None:
        super().__init__(caption=caption, **kwargs)  # parent, directory, filter, options
        self.setFileMode(QFileDialog.DirectoryOnly)
    
    def run_selection_dialog(self) -> Path:
        return super().run_selection_dialog()[0]


class OpenFilesDialog(OpenAnyFileDialog):
    def __init__(self, caption = "Select Files", **kwargs) -> None:
        super().__init__(caption=caption, **kwargs)  # parent, directory, filter, options
        self.setFileMode(QFileDialog.ExistingFiles)
        icon = QApplication.style().standardIcon(QStyle.SP_FileIcon)
        self.setWindowIcon(icon)
