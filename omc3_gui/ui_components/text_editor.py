""" 
UI: Text Editor Dialog
----------------------

This module provides a dialog for editing text files.
"""

from pathlib import Path

from qtpy.QtWidgets import QDialog, QDialogButtonBox, QTextEdit, QVBoxLayout

from omc3_gui.ui_components.message_boxes import show_error_dialog 

class TextEditorDialog(QDialog):
    def __init__(self, file_path: str | Path, title: str = "Edit {}", parent = None):
        super().__init__(parent)
        self.file_path: Path = Path(file_path)
        self.setWindowTitle(title.format(self.file_path.name))  # maybe better absolute path?

        self.text_edit = QTextEdit(self)
        self.load_file_content()

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttons.accepted.connect(self.save_changes)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(self.text_edit)
        layout.addWidget(self.buttons)
        self.setLayout(layout)

    def load_file_content(self):
        try:
            content = self.file_path.read_text()
        except FileNotFoundError:
            return  # empty or new file

        self.text_edit.setPlainText(content)

    def save_changes(self):
        content = self.text_edit.toPlainText()
        try:
            self.file_path.write_text(content)
        except PermissionError:
            show_error_dialog(
                message=f"Could not write to file {self.file_path.absolute()}.",
                title="Permission Error",
                parent=self,
            )
            return
            
        self.accept()