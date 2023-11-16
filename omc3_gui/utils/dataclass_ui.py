import inspect
import re
from dataclasses import MISSING, Field, dataclass, field, fields
from pathlib import Path
from typing import Callable, Dict, Optional, Sequence, Tuple, Union

from qtpy import QtWidgets

from omc3_gui.utils.widgets import HorizontalSeparator


@dataclass
class FieldUIDef:
    name: str
    label: Optional[str] = None
    type: Optional[str] = None
    comment: Optional[str] = None
    editable: Optional[bool] = True



@dataclass
class FieldUI:
    widget: QtWidgets.QWidget
    label: QtWidgets.QLabel
    get_value: Callable
    set_value: Callable
    text_color: Optional[str] = "black"

    def __post_init__(self):
        try:
            self.widget.textChanged.connect(self.has_changed)
        except AttributeError:
            self.widget.valueChanged.connect(self.has_changed)
        self.widget.setStyleSheet(f"color: {self.text_color};")
        self.label.setStyleSheet(f"QLabel {{color: {self.text_color}}};") 

    def has_changed(self):
        font = self.label.font()
        font.setItalic(True)
        self.label.setFont(font)
    
    def reset(self):
        font = self.label.font()
        font.setItalic(False)
        self.label.setFont(font)


@dataclass
class DataClassUI:
    layout: QtWidgets.QGridLayout # layout containing all elements
    model: object = None  # dataclass instance
    fields: Dict[str, FieldUI] = field(default_factory=dict)

    def reset_labels(self):
        for name in self.fields.keys():
            self.fields[name].reset()
    
    def update_widget_from_model(self, name: str):
        value = getattr(self.model, name)
        if value is not None:
            self.fields[name].set_value(value)
    
    def update_model_from_widget(self, name: str):
        value = self.fields[name].get_value()
        setattr(self.model, name, value)

    def update_ui(self):
        for name in self.fields.keys():
            self.update_widget_from_model(name)

    def update_model(self):
        for name in self.fields.keys():
            self.update_model_from_widget(name)


    

class FilePath(Path):
    pass


class DirectoryPath(Path):
    pass


WIDGET_TYPE_MAP = {
    int: QtWidgets.QSpinBox,
    float: QtWidgets.QLineEdit,
    str: QtWidgets.QLineEdit,
    Path: QtWidgets.QLineEdit,
    bool: QtWidgets.QCheckBox,
}


def build_getter_setter(widget, field_type) -> Tuple[Callable, Callable]:
    """ Getter/Setter Factory."""
    if isinstance(widget, QtWidgets.QCheckBox):
        def get_value() -> bool:
            return widget.isChecked()

        def set_value(value: bool):
            widget.setChecked(value)
    
    if isinstance(widget, QtWidgets.QSpinBox):
        def get_value():
            return field_type(widget.value())

        def set_value(value):
            widget.setValue(value)
        
    else:        
        def get_value():
            return field_type(widget.text())

        def set_value(value):
            widget.setText(str(value))
    return get_value, set_value        


def metafield(label: str, comment: str, default=MISSING) -> Field:
    return field(default=default, metadata={"label": label, "comment": comment})


def dataclass_ui_builder(field_def: Sequence[Union[FieldUIDef, str]], dclass: Union[type, object] = None) -> DataClassUI:
    field_instances = {}
    if dclass is not None:
        field_instances = {field.name: field for field in fields(dclass)}

    layout = QtWidgets.QGridLayout()

    dataclass_ui = DataClassUI(layout)
    for idx_row, field in enumerate(field_def):
        if field is None:
            layout.addWidget(HorizontalSeparator(), idx_row, 0, 1, 3)
            continue

        if isinstance(field, str):
            layout.addWidget(QtWidgets.QLabel(field), idx_row, 0)
            continue
        
        if field.name not in field_instances:
            raise ValueError(f"Field {field.name} not found in dataclass {dclass}")
        field_inst = field_instances[field.name]
        
        # Label ---
        qlabel = QtWidgets.QLabel(field.label or field_inst.metadata.get("label", field.name))
        qlabel.setToolTip(field.comment or field_inst.metadata.get("comment", ""))
        layout.addWidget(qlabel, idx_row, 0)
        
        # User input ---
        # If field.type is not given, use evaluate from dataclass. 
        # Check __args__ in case of Union/Optional and use first one.
        # The type needs to be instanciable!
        field_type = field.type or getattr(field_inst.type, "__args__", [field_inst.type])[0]  

        widget = WIDGET_TYPE_MAP.get(field_type, QtWidgets.QLineEdit)()

        try:
            widget.setReadOnly(not field.editable)
        except AttributeError:
            widget.setEnabled(field.editable)

        layout.addWidget(widget, idx_row, 1)

        get_value, set_value = build_getter_setter(widget, field_type)
        dataclass_ui.fields[field.name] = FieldUI(
            widget=widget, 
            label=qlabel,
            set_value=set_value,
            get_value=get_value,
            text_color="#000000" if field.editable else "#bbbbbb"
        )

        # TODO: add path button
    return dataclass_ui


def get_field_inline_comments(dclass: type) -> Dict[str, str]:
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


