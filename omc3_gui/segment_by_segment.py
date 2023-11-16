import sys
from omc3_gui.segment_by_segment.controller import SbSController
from omc3_gui.utils.log_handler import init_logging
import logging

if __name__ == "__main__":
    init_logging()
    sys.exit(SbSController.run_application())