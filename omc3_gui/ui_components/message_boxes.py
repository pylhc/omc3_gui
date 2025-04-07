""" 
UI: Message Boxes
-----------------

Helper functions to display message boxes.
"""
from qtpy.QtWidgets import QMessageBox, QWidget

def show_confirmation_dialog(question: str, title: str = "Confirmation", parent: QWidget = None) -> bool:
    """ Displays a confirmation dialog.

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


def show_error_dialog(message: str, title: str = "Error", parent: QWidget = None):
    """ Displays an error dialog. 
    
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