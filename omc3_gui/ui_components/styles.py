"""
UI: Styles
----------

Helper functions to style UI elements and plots.
"""
from omc3_gui.ui_components import colors

MONOSPACED_TOOLTIP = f"""
    QToolTip {{
        background-color: {colors.TOOLTIP_BACKGROUND}; /* Light gray background */
        color: {colors.TOOLTIP_TEXT}; /* Dark gray text */
        border: 1px solid {colors.TOOLTIP_BORDER}; /* Gray border */
        font-family: "Courier New", monospace; /* Monospaced font */
    }}
"""


def info_panel_style(padding_px: int = 8) -> str:
    """Return a standard style for read-only information panels."""
    return f"padding: {padding_px}px; background-color: {colors.BLACK_12}; border-radius: 5px;"


def status_button_style(is_available: bool) -> str:
    """Return standard style for binary status buttons."""
    if is_available:
        background = colors.GREEN_DARK
    else:
        background = colors.RED_DARK
    return f":enabled {{ background-color: {background}; color: {colors.TEXT_LIGHT}; }}"


def list_widget_text_style(text_color: str = colors.TEXT_DARK) -> str:
    """Return style for list widgets with consistent text color."""
    return f"QListWidget {{ color: {text_color}; }}"


def readonly_table_style(
    text_color: str = colors.TEXT_DARK,
    grid_color: str = colors.BLACK_26,
    header_color: str = colors.BLACK,
) -> str:
    """Return style for read-only summary tables with consistent colors."""
    return (
        f"QTableWidget {{ color: {text_color}; gridline-color: {grid_color}; }} "
        f"QHeaderView::section {{ color: {header_color}; font-weight: 600; }}"
    )