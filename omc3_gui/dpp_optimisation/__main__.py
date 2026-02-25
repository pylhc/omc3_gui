"""
Entry point for DPP Optimisation GUI
-------------------------------------

Run this module to start the Closed Orbit (DPP) Optimisation GUI.
"""
import logging
import sys

from omc3_gui.dpp_optimisation.main_controller import DppOptimisationController


def main():
    """Main entry point for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    return DppOptimisationController.run_application()


if __name__ == "__main__":
    sys.exit(main())
