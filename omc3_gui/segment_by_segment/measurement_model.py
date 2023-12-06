
import logging
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Union

from omc3.model.constants import TWISS_DAT
from omc3.optics_measurements.constants import (BETA_NAME, EXT, KICK_NAME, MODEL_DIRECTORY,
                                                PHASE_NAME)
from tfs.reader import read_headers

from omc3_gui.segment_by_segment.segment_model import SegmentModel
from omc3_gui.utils.dataclass_ui import metafield

SEQUENCE = "SEQUENCE"
DATE = "DATE"
LHC_MODEL_YEARS = (2012, 2015, 2016, 2017, 2018, 2022, 2023)  # TODO: get from omc3

FILES_TO_LOOK_FOR = (f"{name}{plane}" for name in (KICK_NAME, PHASE_NAME, BETA_NAME) for plane in ("x", "y"))

LOGGER = logging.getLogger(__name__)


@dataclass
class OpticsMeasurement:
    """ Class to load and hold the optics-measurement folder. 
    This class also stores the meta-data for the loaded measurement, 
    which can then be passed on to the segment-by-segment.
    The :func:`omc3_gui.utils.dataclass_ui.metafield` is used to provide hints about the fields for the GUI.
    """
    measurement_dir: Path = metafield("Optics Measurement", "Path to the optics-measurement folder")
    model_dir: Path =       metafield("Model",              "Path to the model folder",        default=None)
    accel: str =            metafield("Accelerator",        "Name of the accelerator",         default=None)
    output_dir: Path =      metafield("Output",             "Path to the sbs-output folder",   default=None) 
    corrections: Path =     metafield("Corrections",        "Path to the corrections file",    default=None)
    year: str =             metafield("Year",               "Year of the measurement (model)", default=None, choices=LHC_MODEL_YEARS)
    ring: int =             metafield("Ring",               "Ring of the accelerator",         default=None, choices=(1, 2, 3, 4))
    beam: int =             metafield("Beam",               "Beam of the accelerator",         default=None, choices=(1, 2)) 
    # List of segments. Using a list here, so the name and start/end can be changed
    # without having to modify anything here.
    _segments: List[SegmentModel] = field(default_factory=list)

    DEFAULT_OUTPUT_DIR: ClassVar[str] = "sbs"

    def __post_init__(self):
        if self.output_dir is None:
            self.output_dir = self.measurement_dir / self.DEFAULT_OUTPUT_DIR

    # Visualization ------------------------------------------------------------
    def display(self) -> str:
        return self.measurement_dir.name

    @property
    def id(self) -> str:
        """ Unique identifier for the measurement, used in the GUI. """
        return self.measurement_dir.name

    @classmethod
    def get_label(cls, name: str) -> str:
        try:
            return cls.__dataclass_fields__[name].metadata["label"]
        except KeyError:
            return name

    @classmethod
    def get_comment(cls, name: str) -> str:
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
    def remove_segment(self, segment: SegmentModel):
        self.segments.remove(segment)

    def add_segment(self, segment: SegmentModel):
        if segment in self.segments:
            raise NameError(f"Segment {segment} is already in {self}")
        
        if segment.name in [s.name for s in self.segments]:
            raise NameError(f"A segment with name {segment.name} is already in {self}")

        self.segments.append(segment)
    
    def try_add_segment(self, segment: SegmentModel):
        try:
            self.add_segment(segment)
        except NameError as e:
            LOGGER.error(str(e))
    
    def try_remove_segment(self, segment: SegmentModel):
        try:
            self.remove_segment(segment)
        except ValueError as e:
            LOGGER.error(str(e))
    
    @property
    def segments(self) -> List[SegmentModel]:
        return self._segments

    # Segment-by-Segment Parameters --------------------------------------------
    def get_sbs_parameters(self) -> Dict[str, Any]:
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
    def from_path(cls, path: Path) -> "OpticsMeasurement":
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
                LOGGER.debug(f"{MODEL_DIRECTORY!s} found in {file_name!s}!")
                break

            LOGGER.debug(f"{MODEL_DIRECTORY!s} not found in {file_name!s}.")
    else:
        raise FileNotFoundError(f"Could not find '{MODEL_DIRECTORY}' in any of {FILES_TO_LOOK_FOR!r} in {measurement_path!r}")
    path = Path(headers[MODEL_DIRECTORY])
    LOGGER.debug(f"Associated model dir found: {path!s}")
    return path


def _parse_info_from_model_dir(model_dir: Path) -> Dict[str, Any]:
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
            result['year'] = _get_lhc_model_year(headers.get(DATE))
        elif "psb" in sequence:
            result['accel'] = "psb"
            result['ring'] = int(sequence[-1])
        else:
            result['accel'] = sequence
    LOGGER.debug(f"Associated info found in model dir '{model_dir!s}':\n {result!s}")
    return result


def _get_lhc_model_year(date: Union[str, None]) -> Union[str, None]:
    """ Parses the year from the date in the LHC twiss.dat file 
    and tries to find the closest model-year."""
    if date is None:
        return None
    try:
        found_year = int(f"20{date.split('/')[-1]}")
    except ValueError:
        LOGGER.debug(f"Could not parse year from '{date}'!")
        return None

    for year in sorted(LHC_MODEL_YEARS, reverse=True):
        if year <= found_year:
            LOGGER.debug(f"Assume model year {year!s} from '{date}'!")
            return str(year)
    
    LOGGER.debug(f"Could not parse year from '{date}'!")
    return None
