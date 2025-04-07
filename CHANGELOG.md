# OMC3-GUI Changelog

#### 2025-04-04 - v1.0.0 - Segment-by-Segment GUI

- Maintenance:
  - `pyproject.toml` used instead of `setup.py`.
  - Deactivated testing workflows as there are no tests.
  - Documentation

- Initial release of the Segment-by-Segment GUI:
  - Implements plotting for the Segment-by-Segment propagation of the 
    omc3 backend. Requires `omc3 >= 0.24.0`.
  - Plotting for the SegmentDiffs of `AlphaPhase`, `BetaPhase`, `Dispersion`
    and `Coupling`.
  - Saving and loading of the optics measurements from `.json` files.
  - Create virtual `copy` of the measurements.

- General plotting functionality with `pyqtgraph`:
  - `PlotWidget` to replicate the look-and-feel of the Java-GUI plots.
  - `DualPlotWidget` to handle two plots in one widget (as often the case in our GUIs for two planes).
  - Plotting for pandas Dataframes.
  - Plotting for model elements as vertical lines.

- General reusable Tools:
  - Dataclass UI: Widgets to display and edit dataclasses in UI.
  - Widgets, threads, item models, file dialogs

#### 2023-06-20 - v0.0.0 - Inital commit

- `setup.py` and packaging functionality
- Automated CI:
  - Multiple versions of python
  - Accuracy tests
  - Unit tests
  - Release automation
