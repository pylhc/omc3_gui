""" 
Measurement Model
-----------------

This module contains the model for the Optics Measurement 
in the Segment-by-Segment application.
"""
from __future__ import annotations

import json
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
from omc3.segment_by_segment.constants import corrections_madx
from tfs.reader import read_headers

from omc3_gui.ui_components.dataclass_ui import DirectoryPath, FilePath, metafield
from omc3_gui.ui_components.dataclass_ui import choices_validator as choices
from omc3_gui.ui_components.dataclass_ui.tools import (
    load_dataclass_from_json,
    save_dataclass_to_json,
    update_dataclass_from_json,
)

if TYPE_CHECKING:
    from omc3_gui.segment_by_segment.segment_model import SegmentDataModel

SEQUENCE: str = "SEQUENCE"
DATE: str = "DATE"

FILES_TO_LOOK_FOR: tuple[str, ...] = tuple(f"{name}{plane}" for name in (KICK_NAME, PHASE_NAME, BETA_NAME) for plane in ("x", "y"))
TO_BE_DEFINED: str = "to_be_defined"


LOGGER = logging.getLogger(__name__)


def exists(value: Path | None) -> bool:
    return value is not None and value.exists()


@dataclass(slots=True)
class OpticsMeasurement:
    """ Class to load and hold the optics-measurement folder. 
    This class also stores the meta-data for the loaded measurement, 
    which can then be passed on to the segment-by-segment.
    The :func:`omc3_gui.utils.dataclass_ui.metafield` is used to provide hints about the fields for the GUI.
    """
    measurement_dir: DirectoryPath = metafield("Optics Measurement", "Path to the optics-measurement folder", default=Path(TO_BE_DEFINED), validate=exists)
    model_dir: DirectoryPath =       metafield("Model",              "Path to the model folder",        default=Path(TO_BE_DEFINED), validate=exists)
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
    JSON_FILENAME: ClassVar[str] = "sbs_measurement.json"

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
        size = max(len(name) for name, _ in parts)
        return "\n".join(f"{name:{size}s}: {value}" for name, value in parts if value is not None)

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
    
    def try_add_segment(self, segment: SegmentDataModel, silent: bool = False) -> bool:
        try:
            self.add_segment(segment)
        except NameError as e:
            if silent:
                LOGGER.debug(str(e))
            else: 
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
    def copy(self) -> OpticsMeasurement:
        """ Creates a copy of the measurement. """
        new_measurement = OpticsMeasurement(
            **{
                f.name: getattr(self, f.name) for f in fields(self) 
                if not f.name.startswith("_")
            },
        )
        for segment in self.segments:
            new_segment = segment.copy()
            new_segment.measurement = new_measurement
            new_measurement.add_segment(new_segment)
        return new_measurement

    @classmethod
    def from_path(cls, path: Path) -> OpticsMeasurement:
        """ Creates an OpticsMeasurement from a folder, by trying 
        to parse information from the data in the folder.

        Args:
            path (Path): Path to the folder.

        Returns:
            OpticsMeasurement: OpticsMeasurement instance. 
        """
        # Try to load from json first ---
        json_path = None
        default_json_path = path / cls.JSON_FILENAME
        default_output_json_path = path / cls.DEFAULT_OUTPUT_DIR / cls.JSON_FILENAME
        measurement_path = None
        if (default_json_path).is_file():
            json_path = default_json_path
            if any((path / f).is_file() for f in FILES_TO_LOOK_FOR):
                measurement_path = path  # otherwise probably an output dir
        elif(default_output_json_path).is_file():
            json_path = default_output_json_path
            measurement_path = path
        
        if json_path is not None:
            try:
                return cls.from_json(json_path, measurement_path)
            except json.decoder.JSONDecodeError as e:
                LOGGER.error(f"JSON errror: {e!s}\nTrying to load as optics-measurement folder.")

        # Try to load from optics-measurement folder ---
        info = {}
        try:
            model_dir = _parse_model_dir_from_optics_measurement(path)
        except FileNotFoundError as e:
            LOGGER.error(str(e))
        else:
            info = _parse_info_from_model_dir(model_dir)
            info["model_dir"] = model_dir
        
        if (path / corrections_madx).is_file():
            info["corrections"] = path / corrections_madx
        
        return cls(measurement_dir=path, **info)
    
    @classmethod
    def from_json(cls, path: Path, measurement_dir: Path | None = None) -> OpticsMeasurement:
        """ Creates an OpticsMeasurement from a folder, by trying 
        to parse information from the data in the folder.

        Args:
            path (Path): Path to the folder.

        Returns:
            OpticsMeasurement: OpticsMeasurement instance. 
        """
        if measurement_dir is not None:
            meas: OpticsMeasurement = cls(measurement_dir=measurement_dir)
            meas = update_dataclass_from_json(meas, path)
            meas.measurement_dir = measurement_dir  # in case the folder name/path changed since the json was written
            return meas
        return load_dataclass_from_json(cls, path)

    def to_json(self, path: Path | None = None) -> None:
        if path is None:
            if self.output_dir is not None:
                self.output_dir.mkdir(parents=True, exist_ok=True)
                path = self.output_dir / self.JSON_FILENAME
            else:
                if self.measurement_dir is None or self.measurement_dir == TO_BE_DEFINED:
                    raise ValueError("Measurement dir is still to be defined.")
                path = self.measurement_dir / self.JSON_FILENAME
        save_dataclass_to_json(self, path)
    
    def quick_check(self) -> None:
        """ Tests for completeness of the definition (e.g. after loading). """
        if self.measurement_dir is None or self.measurement_dir == TO_BE_DEFINED:
            raise NameError("Measurement dir is still to be defined.")  # BAD

        if any(getattr(self, name) is None for name in ("model_dir", "accel", "output_dir")) or self.model_dir == TO_BE_DEFINED:
            raise ValueError(f"Current definition of '{self.measurement_dir!s}' is incomplete. Adjust manually!!")

        if self.accel == 'lhc' and (self.year is None or self.beam is None):
            raise ValueError(f"Current definition of '{self.measurement_dir!s}' for LHC is incomplete. Adjust manually!!")        
        
        if self.accel == 'psb' and self.ring is None:
            raise ValueError(f"Current definition of '{self.measurement_dir!s}' for PSB is incomplete. Adjust manually!!")


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
            result['year'] = map_lhc_year(_get_year_from_header(headers))
        elif "psb" in sequence:
            result['accel'] = "psb"
            result['ring'] = int(sequence[-1])
        else:
            result['accel'] = sequence
    LOGGER.debug(f"Associated info found in model dir '{model_dir!s}':\n {result!s}")
    return result


def _get_year_from_header(headers: dict) -> str | None:
    """ Parses the year from the date in the twiss.dat file.
    
    TODO: Will not work for hl-lhc models. These should return the hl-version.
    """
    date = headers.get(DATE)
    
    if date is None:
        return None

    year = f"20{date.split('/')[-1]}"
    LOGGER.debug(f"Assuming model year {year!s} from '{date}'!")
    return year


def map_lhc_year(year: str | None) -> str:
    """ Maps the input year to the corresponding available model year. """
    if year is None:
        return None
    
    try:
        int_year = int(year)
    except ValueError:
        return year
    
    # no new models (see omc/model/accelerators/lhc)
    if 2012 < int_year < 2015:  
        LOGGER.info(f"Mapping year {year} to LHC model 2012!")
        return "2012"
    
    # no new models (there was a 2021 in acc-models, but we were not using it then)
    if 2018 < int_year < 2022:  
        LOGGER.info(f"Mapping year {year} to LHC model 2018!")
        return "2018"
    
    return year
    