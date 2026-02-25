"""
UI: Message Boxes
-----------------

Helper functions to display message boxes.
"""

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QMessageBox, QWidget


def show_confirmation_dialog(
    question: str, title: str = "Confirmation", parent: QWidget | None = None
) -> bool:
    """Displays a confirmation dialog.

    Could also be done with QMessageBox.question(parent, title, question, QMessageBox.Ok | QMessageBox.Cancel).

    Args:
        question (str): Dialog question.
        title (str): Dialog title.
        parent (QtWidgets.QWidget): Parent widget.

    Returns:
        bool: True if the user confirmed, False otherwise
    """
    msg_box = QMessageBox(
        QMessageBox.Question,
        title,
        question,
        QMessageBox.Ok | QMessageBox.Cancel,
        parent
    )
    msg_box.setDefaultButton(QMessageBox.Cancel)
    result = msg_box.exec_()
    return result == QMessageBox.Ok


def show_error_dialog(message: str, title: str = "Error", parent: QWidget | None = None):
    """Displays an error dialog.

    This is a convenience function to displays an error dialog.

    Args:
        title (str): Dialog title.
        message (str): Dialog message.
        parent (QtWidgets.QWidget): Parent widget.
    """
    message_box = QMessageBox(
        QMessageBox.Critical,
        title,
        message,
        QMessageBox.Ok,
        parent,
    )
    message_box.exec_()


def show_info_dialog(message: str, title: str = "Information", parent: QWidget | None = None):
    """Displays an information dialog.

    This is a convenience function to display an information dialog.

    Args:
        title (str): Dialog title.
        message (str): Dialog message.
        parent (QtWidgets.QWidget): Parent widget.
    """
    message_box = QMessageBox(
        QMessageBox.Information,
        title,
        message,
        QMessageBox.Ok,
        parent,
    )
    message_box.exec_()


def show_rich_info_dialog(
    message_html: str,
    title: str = "Information",
    parent: QWidget | None = None,
):
    """Displays an information dialog with rich-text message content."""
    message_box = QMessageBox(
        QMessageBox.Information,
        title,
        "",
        QMessageBox.Ok,
        parent,
    )
    message_box.setTextFormat(Qt.TextFormat.RichText)
    message_box.setText(message_html)
    message_box.exec_()