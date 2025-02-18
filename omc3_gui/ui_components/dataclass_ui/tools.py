""" 
DataClass UI: Tools 
-------------------

Additional tools that can be used with dataclasses.
"""
from __future__ import annotations

import inspect
import logging
import re


LOGGER = logging.getLogger(__name__)


def get_field_inline_comments(dclass: type) -> dict[str, str]:
    """
    Returns a dictionary mapping field names to their associated inline code-comments.
    Has been replaced by the use of the metadata, but I like the function,
    so I leave it here. (jdilly 2023)

    Parameters:
        dclass (type): The data class to extract field comments from.

    Returns:
        Dict[str, str]: A dictionary mapping field names to their associated comments.
    """
    matcher = re.compile(r"^(?P<field>[a-zA-Z_]+)\s*:\s*[^#]+#\s*(?P<comment>.*)\s*$")
    source = inspect.getsource(dclass)

    found_fields = {}
    for line in source.splitlines()[2:]:  # first two is @dataclass and name
        line = line.strip()
        if line.startswith('def '):
            break

        match = matcher.match(line)
        if match:
            found_fields[match.group('field')] = match.group('comment')

    return found_fields
