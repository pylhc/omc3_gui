""" 
UI: DataClasses
---------------

This module provides classes to generate simple UI's for dataclasses,
which allow to edit the values of dataclasses in a simple way.
"""
from __future__ import annotations

import dataclasses as dc
import inspect
import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import MISSING, Field, dataclass, field, fields
from functools import partial
from pathlib import Path
from typing import Any, Protocol, get_type_hints

from qtpy import QtWidgets

from omc3_gui.ui_components import colors, file_dialogs
from omc3_gui.ui_components.widgets import HorizontalSeparator

LOGGER = logging.getLogger(__name__)


# Helper for the dataclass definitions -----------------------------------------



# View -------------------------------------------------------------------------


# Other ------------------------------------------------------------------------

