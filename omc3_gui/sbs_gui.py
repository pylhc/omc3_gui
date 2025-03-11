""" 
Segment-by-Segment GUI
----------------------

Graphical user interface to run the Segment-by-Segment propagation.
"""
from argparse import ArgumentParser
from pathlib import Path
import sys
from omc3_gui.segment_by_segment.main_controller import SbSController
from omc3_gui.segment_by_segment.settings import Settings
from omc3_gui.utils.log_handler import init_logging

# --- For QT Debugging ----------------
# import os
# os.environ["QT_DEBUG_PLUGINS"] = "1"
# -------------------------------------


def parse_args() -> tuple[list[Path], Settings]:
    args = ArgumentParser()
    args.add_argument(
        "-m",
        "--measurements",
        nargs="+",
        type=Path,
        help="Measurements to process",
    )
    args.add_argument(
        "-s",
        "--settings",
        type=Path,
        help="Settings file to use",
    )
    opt = args.parse_args()
    return opt.measurements,  opt.settings


if __name__ == "__main__":
    init_logging()
    measurements, settings = parse_args()
    sys.exit(SbSController.run_application(
        measurements=measurements, 
        settings=settings
    ))