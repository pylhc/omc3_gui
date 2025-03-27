""" 
DataClass UI: Tools 
-------------------

Additional tools that can be used with dataclasses.
"""
from __future__ import annotations

from dataclasses import Field, fields
import inspect
import json
import logging
from pathlib import Path
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


# JSON -------------------------------------------------------------------------

# Load ---

def load_dataclass_from_json(
    dclass: type, 
    json_file: str | Path
):
    """
    Load a dataclass from a JSON file.
    Selects only the fields that are in the dataclass. Ignores fields that start with an underscore.

    Parameters:
        dclass (type): The data class to load from the JSON file.
        json_file (str): The path to the JSON file to load the data class from.

    Returns:
        object: An instance of the data class loaded from the JSON file.
    """
    return dclass(**_load_json_file(json_file, dclass))


def update_dataclass_from_json(
    data: object, 
    json_file: str | Path
):
    """
    Update a dataclass with data from a JSON file.
    Selects only the fields that are in the dataclass and json file. 
    Ignores fields that start with an underscore.

    Parameters:
        dclass (object): The data class instance to update from to the JSON file.
        json_file (str): The path to the JSON file to load the data from.

    Returns:
        object: An instance of the data class loaded from the JSON file.
    """
    json_data = _load_json_file(json_file, data)
    for key, value in json_data.items(): 
        setattr(data, key, value)
    return data


def _load_json_file(json_file: str | Path, dclass: object | type | None = None) -> dict:
    """ Load a JSON file and return a dictionary of the data. 
    The data is converted to a path if the field type requires it and filtered if the field name 
    is either not in the dataclass or starts with an underscore. """
    data: dict = json.loads(json_file.read_text())
    if dclass is None:
        return data
    return {f.name: _maybe_path(data.get(f.name, None), f) for f in fields(dclass) if f.name[0] != "_"}


def _maybe_path(value: str | Path, field: Field) -> Path:
    """ Convert value to a path, if the field type requires it. """

    if isinstance(field.type, str):
        if "Path" in field.type and value is not None:
            return Path(value)
        return value
    
    if issubclass(field.type, Path) and value is not None:
        return Path(value)
    return value


# Save ----

def save_dataclass_to_json(
    data: object, 
    json_file: str | Path
):
    """
    Save a dataclass to a JSON file.
    Ignores fields that start with an underscore.

    Parameters:
        dclass (object): The data class instance to save to the JSON file.
        json_file (str): The path to the JSON file to save the data class to.
    """
    data = {f.name: getattr(data, f.name) for f in fields(data) if f.name[0] != "_"}
    for key, value in data.items():
        if isinstance(value, Path):
            data[key] = str(value)
    json_file.write_text(f"{json.dumps(data, indent=2)}\n")
