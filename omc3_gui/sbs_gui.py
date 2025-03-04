""" 
Segment-by-Segment GUI
----------------------

Graphical user interface to run the Segment-by-Segment propagation.
"""
import sys
from omc3_gui.segment_by_segment.main_controller import SbSController
from omc3_gui.utils.log_handler import init_logging

# --- For QT Debugging ----------------
# import os
# os.environ["QT_DEBUG_PLUGINS"] = "1"
# -------------------------------------

if __name__ == "__main__":
    init_logging()
    sys.exit(SbSController.run_application())