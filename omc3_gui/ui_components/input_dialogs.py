"""
UI: Input Dialogs
-----------------

Helper wrappers for common input dialogs.
"""
from __future__ import annotations

from collections.abc import Sequence

from qtpy.QtWidgets import QInputDialog, QWidget


def ask_text_dialog(
    parent: QWidget,
    title: str,
    label: str,
    text: str = "",
) -> tuple[str, bool]:
    """Open a text input dialog and return entered text and acceptance state."""
    return QInputDialog.getText(parent, title, label, text=text)


def ask_item_dialog(
    parent: QWidget,
    title: str,
    label: str,
    items: Sequence[str],
    editable: bool = False,
    current: int = 0,
) -> tuple[str, bool]:
    """Open an item selection dialog and return selected item and acceptance state."""
    return QInputDialog.getItem(
        parent,
        title,
        label,
        list(items),
        current=current,
        editable=editable,
    )


def ask_double_dialog(
    parent: QWidget,
    title: str,
    label: str,
    value: float,
    min_value: float = 0.0,
    max_value: float = 1_000_000.0,
    decimals: int = 3,
) -> tuple[float, bool]:
    """Open a floating-point input dialog and return value and acceptance state."""
    return QInputDialog.getDouble(
        parent,
        title,
        label,
        value=value,
        min=min_value,
        max=max_value,
        decimals=decimals,
    )
