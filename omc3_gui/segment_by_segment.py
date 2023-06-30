import logging
import sys
from pathlib import Path

from qtpy import QtWidgets

from omc3_gui.segment_by_segment_matcher.constants import LHC_MODES
from omc3_gui.segment_by_segment_matcher.main import SbSGuiMainController
from omc3_gui.utils import log_handler

LOGGER = logging.getLogger(__name__)


def main(lhc_mode=None, match_path=None, input_dir=None):
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("fusion")
    main_controller = SbSGuiMainController()
    if match_path is None or lhc_mode is None:
        lhc_mode, match_path = main_controller.ask_for_initial_config(
            lhc_mode,
            match_path,
        )
        if match_path is None or lhc_mode is None:
            return
    match_path = Path(match_path)
    log_handler.add_file_handler(match_path)
    if lhc_mode not in LHC_MODES:
        raise ValueError(f"Invalid lhc mode, must be one of {LHC_MODES!s}")
    LOGGER.info("-------------------- ")
    LOGGER.info("Configuration:")
    LOGGER.info(f"- LHC mode: {lhc_mode!s}")
    LOGGER.info(f"- Match output path: {match_path!s}")
    LOGGER.info("-------------------- ")
    main_controller.set_match_path(match_path)
    main_controller.set_lhc_mode(lhc_mode)
    main_controller.set_input_dir(input_dir)
    main_controller.show_view()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main(lhc_mode="lhcb1", match_path=Path("/mnt/volume/jdilly/temp/"))
