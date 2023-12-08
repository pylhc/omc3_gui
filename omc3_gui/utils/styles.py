
from omc3_gui.utils import colors

MONOSPACED_TOOLTIP = f"""
    QToolTip {{
        background-color: {colors.TOOLTIP_BACKGROUND}; /* Light gray background */
        color: {colors.TOOLTIP_TEXT}; /* Dark gray text */
        border: 1px solid {colors.TOOLTIP_BORDER}; /* Gray border */
        font-family: "Courier New", monospace; /* Monospaced font */
    }}
"""