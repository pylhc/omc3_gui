""" 
Measurement Model
-----------------

This module contains the model for the Optics Measurement 
in the Segment-by-Segment application.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from omc3.model.constants import TWISS_DAT
from omc3.optics_measurements.constants import (
    BETA_NAME,
    EXT,
    KICK_NAME,
    MODEL_DIRECTORY,
    PHASE_NAME,
)
from tfs.reader import read_headers

from omc3_gui.ui_components.dataclass_ui import choices_validator as choices
from omc3_gui.ui_components.dataclass_ui import metafield, DirectoryPath, FilePath

if TYPE_CHECKING:
    from omc3_gui.segment_by_segment.segment_model import SegmentDataModel

SEQUENCE: str = "SEQUENCE"
DATE: str = "DATE"

FILES_TO_LOOK_FOR: tuple[str, ...] = tuple(f"{name}{plane}" for name in (KICK_NAME, PHASE_NAME, BETA_NAME) for plane in ("x", "y"))

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class OpticsMeasurement:
    """ Class to load and hold the optics-measurement folder. 
    This class also stores the meta-data for the loaded measurement, 
    which can then be passed on to the segment-by-segment.
    The :func:`omc3_gui.utils.dataclass_ui.metafield` is used to provide hints about the fields for the GUI.
    """
    measurement_dir: DirectoryPath = metafield("Optics Measurement", "Path to the optics-measurement folder")
    model_dir: DirectoryPath =       metafield("Model",              "Path to the model folder",        default=None)
    accel: str =                     metafield("Accelerator",        "Name of the accelerator",         default=None)
    output_dir: DirectoryPath =      metafield("Output",             "Path to the sbs-output folder",   default=None) 
    corrections: FilePath =          metafield("Corrections",        "Path to the corrections file",    default=None)
    year: str =                      metafield("Year",               "Year of the measurement (model)", default=None)
    ring: int =                      metafield("Ring",               "Ring of the accelerator",         default=None, validate=choices(1, 2, 3, 4))
    beam: int =                      metafield("Beam",               "Beam of the accelerator",         default=None, validate=choices(1, 2)) 
    # List of segments. Using a list here, so the name and start/end can be changed
    # without having to modify anything here.
    _segments: list[SegmentDataModel] = field(default_factory=list)

    DEFAULT_OUTPUT_DIR: ClassVar[str] = "sbs"

    def __post_init__(self):
        if self.output_dir is None:
            self.output_dir = self.measurement_dir / self.DEFAULT_OUTPUT_DIR

    # Visualization ------------------------------------------------------------
    def display(self) -> str:
        if self.output_dir.name == self.DEFAULT_OUTPUT_DIR:
            return self.measurement_dir.name
        return f"{self.measurement_dir.name} -> {self.output_dir.name}"

    @property
    def id(self) -> str:
        """ Unique identifier for the measurement, used in the ItemModel. """
        return str(self.output_dir)

    @classmethod
    def get_label(cls, name: str) -> str:
        """ Returns the label for the field named `name`. """
        try:
            return cls.__dataclass_fields__[name].metadata["label"]
        except KeyError:
            return name

    @classmethod
    def get_comment(cls, name: str) -> str:
        """ Returns the comment for the field named `name`. """
        try:
            return cls.__dataclass_fields__[name].metadata["comment"]
        except KeyError:
            return ""

    def tooltip(self) -> str:
        """ Returns a string with information about the measurement, 
        as to be used in a tool-tip.  """
        parts = [
            (self.get_label(f.name), getattr(self, f.name)) for f in fields(self) 
            if not f.name.startswith("_")
        ]
        l = max(len(name) for name, _ in parts)
        return "\n".join(f"{name:{l}s}: {value}" for name, value in parts if value is not None)

    # Segment Control ----------------------------------------------------------
    def remove_segment(self, segment: SegmentDataModel):
        try:
            self.segments.remove(segment)
        except ValueError as e:
            raise ValueError(f"Segment with name {segment.name} is not in {self.display()}.") from e

    def add_segment(self, segment: SegmentDataModel):
        if segment in self.segments:
            raise NameError(f"Segment {segment} is already in {self.display()}")
        
        if segment.name in [s.name for s in self.segments]:
            raise NameError(f"A segment with name {segment.name} is already in {self.display()}")

        self.segments.append(segment)
    
    def try_add_segment(self, segment: SegmentDataModel) -> bool:
        try:
            self.add_segment(segment)
        except NameError as e:
            LOGGER.error(str(e))
            return False
        return True
    
    def try_remove_segment(self, segment: SegmentDataModel | str) -> bool:
        if isinstance(segment, str):
            try:
                segment = self.get_segment_by_name(segment)
            except NameError as e:
                LOGGER.error(str(e))
                return False

        try:
            self.remove_segment(segment)
        except ValueError as e:
            LOGGER.error(str(e))
            return False
        return True
    
    def get_segment_by_name(self, name: str) -> SegmentDataModel:
        for segment in self.segments:
            if segment.name == name:
                return segment

        msg = f"No segment with name {name} in {self.display()}."
        raise NameError(msg)
        
    @property
    def segments(self) -> list[SegmentDataModel]:
        return self._segments

    # Segment-by-Segment Parameters --------------------------------------------
    def get_sbs_parameters(self) -> dict[str, Any]:
        parameters = dict(
            measurement_dir=self.measurement_dir,
            corrections=self.corrections,
            output_dir=self.output_dir,
            accel = self.accel,
            model_dir = self.model_dir,
        )
        if self.beam is not None:
            parameters["beam"] = self.beam
        if self.year is not None:
            parameters["year"] = self.year
        if self.ring is not None:
            parameters["ring"] = self.ring 
        return parameters

    # Builder ------------------------------------------------------------------
    @classmethod
    def from_path(cls, path: Path) -> OpticsMeasurement:
        """ Creates an OpticsMeasurement from a folder, by trying 
        to parse information from the data in the folder.

        Args:
            path (Path): Path to the folder.

        Returns:
            OpticsMeasurement: OpticsMeasurement instance. 
        """
        model_dir = None
        info = {}
        try:
            model_dir = _parse_model_dir_from_optics_measurement(path)
        except FileNotFoundError as e:
            LOGGER.error(str(e))
        else:
            info = _parse_info_from_model_dir(model_dir)
        
        meas = cls(measurement_dir=path, model_dir=model_dir, **info)
        if (
            any(getattr(meas, name) is None for name in ("model_dir", "accel", "output_dir")) 
            or (meas.accel == 'lhc' and (meas.year is None or meas.beam is None))
            or (meas.accel == 'psb' and meas.ring is None)
        ):
            LOGGER.error(f"Info parsed from measurement folder '{path!s}' is incomplete. Adjust manually!!") 
            # TODO: Popup error message as well?
        return meas


def _parse_model_dir_from_optics_measurement(measurement_path: Path) -> Path:
    """Tries to find the model directory in the headers of one of the optics measurement files.

    Args:
        measurement_path (Path): Path to the folder. 

    Returns:
        Path: Path to the (associated) model directory. 
    """
    LOGGER.debug(f"Searching for model dir in {measurement_path!s}")
    for file_name in FILES_TO_LOOK_FOR:
        LOGGER.debug(f"Checking {file_name!s} for model dir.")
        try:
            headers = read_headers((measurement_path / file_name).with_suffix(EXT))
        except FileNotFoundError:
            LOGGER.debug(f"{file_name!s} not found in {measurement_path!s}.")
        else:
            if MODEL_DIRECTORY in headers:
                LOGGER.debug(f"{MODEL_DIRECTORY!s} found in {file_name!s}: {headers[MODEL_DIRECTORY]!s}!")
                return Path(headers[MODEL_DIRECTORY])

            LOGGER.debug(f"{MODEL_DIRECTORY!s} not found in {file_name!s}.")
    raise FileNotFoundError(f"Could not find '{MODEL_DIRECTORY}' in any of {FILES_TO_LOOK_FOR!r} in {measurement_path!r}")


def _parse_info_from_model_dir(model_dir: Path) -> dict[str, Any]:
    """ Checking twiss.dat for more info about the accelerator.

    Args:
        model_dir (Path): Path to the model-directory. 

    Returns:
        Dict[str, Any]: Containing the additional info found (accel, beam, year, ring). 
    """
    result = {}

    try:
        headers = read_headers(model_dir / TWISS_DAT)
    except FileNotFoundError as e:
        LOGGER.debug(str(e))
        return result

    sequence = headers.get(SEQUENCE)
    if sequence is not None:
        sequence = sequence.lower()
        if "lhc" in sequence:
            result['accel'] = "lhc"
            result['beam'] = int(sequence[-1])
            result['year'] = _get_year_from_header(headers)
        elif "psb" in sequence:
            result['accel'] = "psb"
            result['ring'] = int(sequence[-1])
        else:
            result['accel'] = sequence
    LOGGER.debug(f"Associated info found in model dir '{model_dir!s}':\n {result!s}")
    return result


def _get_year_from_header(headers: dict) -> str | None:
    """ Parses the year from the date in the LHC twiss.dat file."""
    date = headers.get(DATE)
    
    if date is None:
        return None

    year = f"20{date.split('/')[-1]}"
    LOGGER.debug(f"Assume model year {year!s} from '{date}'!")
    return year
    
