""" 
UI: Colors
----------

This module contains the color definitions for the application.
All colors should be defined here for consistency and the elements
will then refer to the main color-constants, e.g. `colors.TEXT_DARK` 
(not to the colors themselves).
This allows for a unified look and feel.
"""
import logging

# Predefined Colors ---
BLACK: str = "#000000"
BLACK_87: str = "#212121"
BLACK_54: str = "#757575"
BLACK_38: str = "#9e9e9e"
BLACK_26: str = "#bdbdbd"
BLACK_12: str = "#e1e1e1"
WHITE: str = "#FFFFFF"

GREEN: str = "#00FF00"
GREEN_DARK: str = "#28642A"
GREEN_LIGHT: str = "#4CAF50"
GREEN_DARK_GREY: str = "#8EA18F"
GREEN_LIGHT_GREY: str = "#C8E6C9"

RED: str = "#FF0000"
RED_DARK: str = "#B71C1C"
RED_LIGHT: str = "#F44336"
RED_GREY: str = "#CFADAD"

BLUE: str = "#0000FF"
BLUE_DARK: str = "#0D47A1"
BLUE_LIGHT: str = "#2196F3"
BLUE_GREY: str = "#9FA8DA"

ORANGE_DARK: str = "#E65100"
ORANGE_LIGHT: str = "#FF9800"
ORANGE_GREY: str = "#F9E0B3"

PURPLE_DARK: str = "#4A148C"
PURPLE_LIGHT: str = "#9C27B0"
PURPLE_GREY: str = "#D1C4E9"

CORAL: str = "#E91E63"

# Machine Colors ---
# LHC Colors
BEAM1: str = BLUE
BEAM2: str = RED

# PSB Ring Colors
RING1: str = GREEN_LIGHT
RING2: str = ORANGE_LIGHT
RING3: str = PURPLE_DARK
RING4: str = CORAL

# Light Background, dark text ---
TEXT_DARK: str = BLACK_87
SECONDARY_TEXT_DARK: str = BLACK_54
GREYED_OUT_TEXT_DARK: str = BLACK_26

# Dark Background, light text ---
TEXT_LIGHT: str = WHITE
SECONDARY_TEXT_LIGHT: str = BLACK_12

# Tooltips ---
TOOLTIP_TEXT: str = BLACK_87
TOOLTIP_BACKGROUND: str = BLACK_12
TOOLTIP_BORDER: str = BLACK_38

# Logging ---
LOGGING: dict[int, str] = {
    logging.DEBUG: BLACK_26,        # default: black 
    logging.INFO: BLACK_87,         # default: green
    # logging.WARNING: ORANGE_LIGHT,  # default: orange
    # logging.ERROR: RED_DARK,        # default: red
    # logging.CRITICAL: CORAL,   
}