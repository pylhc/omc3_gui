

from argparse import ArgumentParser
from dataclasses import fields, is_dataclass

from omc3_gui.ui_components.dataclass_ui import get_dataclass_types



def get_argument_parser(dclass: type | object, parser: ArgumentParser | None = None, prefix: str = "") -> ArgumentParser:
    """ Create an argument parser for the given dataclass.
    Makes use of the field metadata, in particular a `comment` field.
    """
    if parser is None:
        parser = ArgumentParser()

    for field in fields(dclass):
        if field.name[0] == "_":
            continue

        if is_dataclass(field.type):
            get_argument_parser(field.type, parser, f"{prefix}{field.name}.")    
            continue
        
        parser.add_argument(
            f"--{prefix}{field.name}", 
            default=field.default, 
            help=field.metadata.get("comment")
        )

    return parser


def from_dict(dclass: type | object, d: dict) -> object:
    field_types = get_dataclass_types(dclass, [field.name for field in fields(dclass)])

    # Convert all sub-fields to dataclasses
    for field in fields(dclass):
        if not is_dataclass(field.type):
            continue

        prefix = f"{field.name}."
        sub_dict = {key.replace(prefix, "", 1): value for key, value in d.items() if key.startswith(prefix)}
        d[field.name] = from_dict(field.type, sub_dict)
    
    return dclass(**d)
