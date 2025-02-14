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