""" 
Segment-by-Segment GUI
----------------------

Graphical user interface to run the Segment-by-Segment propagation.


TODO:
 
 GUI:
 - Load segments from file or folder (check sbs/sbs_ files)
 - Save segments to file
 - Autoload segments when opening measurement folder
 - Pass measurement folders via cli args.

Settings:
 - Save settings to json file
 - Load settings from file
 - Pass path to settings file as cli arg and load on startup

Plotting:
 - Going back through plot history on double-click

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
    sys.exit(SbSController.run_application(measurements=["/mnt/volume/jdilly/projects/omc3_gui/tst_SBStest_wACD/measured_optics"]))