"""
Arc Configuration Dialog
-------------------------

Dialog for configuring a single arc's BPM and magnet range settings.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from qtpy import QtWidgets
from qtpy.QtCore import Qt

from omc3_gui.dpp_optimisation.main_model import ArcConfigData, BpmInfo
from omc3_gui.ui_components import colors
from omc3_gui.ui_components.widgets import DefaultButton

LOGGER = logging.getLogger(__name__)


class ArcConfigDialog(QtWidgets.QDialog):
    """Dialog for configuring arc parameters."""

    def __init__(
        self,
        arc_config: Optional[ArcConfigData],
        bpms: list[BpmInfo],
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Arc Configuration")
        self.setModal(True)
        self.resize(600, 400)

        self._bpms = bpms
        self._bpm_lookup = {bpm.name: bpm.s_position for bpm in self._bpms}
        self._max_bpm_s = max((bpm.s_position for bpm in self._bpms), default=0.0)
        self._arc_config = arc_config or ArcConfigData(name="New Arc", magnet_range_start_bpm="", magnet_range_end_bpm="")

        self._build_ui()
        self._load_data()

    def _build_ui(self):
        """Build the user interface."""
        layout = QtWidgets.QVBoxLayout(self)

        # Arc Name
        name_layout = QtWidgets.QHBoxLayout()
        name_layout.addWidget(QtWidgets.QLabel("Arc Name:"))
        self._name_edit = QtWidgets.QLineEdit()
        name_layout.addWidget(self._name_edit)
        layout.addLayout(name_layout)

        # Magnet Range Section
        magnet_group = QtWidgets.QGroupBox("Magnet Range")
        magnet_layout = QtWidgets.QFormLayout()

        # Start BPM
        self._start_bpm_combo = QtWidgets.QComboBox()
        self._start_bpm_combo.addItems([bpm.name for bpm in self._bpms])
        self._start_bpm_combo.setEditable(True)
        magnet_layout.addRow("Start BPM:", self._start_bpm_combo)

        # Start S Position (read-only, auto-updated)
        self._start_s_label = QtWidgets.QLabel("0.0")
        magnet_layout.addRow("Start S Position (m):", self._start_s_label)

        # End BPM
        self._end_bpm_combo = QtWidgets.QComboBox()
        self._end_bpm_combo.addItems([bpm.name for bpm in self._bpms])
        self._end_bpm_combo.setEditable(True)
        magnet_layout.addRow("End BPM:", self._end_bpm_combo)

        # End S Position (read-only, auto-updated)
        self._end_s_label = QtWidgets.QLabel("0.0")
        magnet_layout.addRow("End S Position (m):", self._end_s_label)

        # Double Slider for S Position
        slider_layout = QtWidgets.QVBoxLayout()
        slider_layout.addWidget(QtWidgets.QLabel("Adjust Range by S Position:"))

        # Create a widget to hold both sliders
        slider_widget = QtWidgets.QWidget()
        slider_widget_layout = QtWidgets.QVBoxLayout(slider_widget)
        slider_widget_layout.setContentsMargins(0, 0, 0, 0)

        self._start_slider = QtWidgets.QSlider(Qt.Horizontal)
        self._start_slider.setMinimum(0)
        self._start_slider.setMaximum(1000)  # Will be set based on max S
        self._start_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)

        self._end_slider = QtWidgets.QSlider(Qt.Horizontal)
        self._end_slider.setMinimum(0)
        self._end_slider.setMaximum(1000)
        self._end_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)

        slider_widget_layout.addWidget(QtWidgets.QLabel("Start:"))
        slider_widget_layout.addWidget(self._start_slider)
        slider_widget_layout.addWidget(QtWidgets.QLabel("End:"))
        slider_widget_layout.addWidget(self._end_slider)

        slider_layout.addWidget(slider_widget)
        magnet_layout.addRow(slider_layout)

        magnet_group.setLayout(magnet_layout)
        layout.addWidget(magnet_group)

        # BPM Selection Section
        bpm_group = QtWidgets.QGroupBox("BPM Selection Parameters")
        bpm_layout = QtWidgets.QFormLayout()

        # BPM Step
        self._bpm_step_spin = QtWidgets.QSpinBox()
        self._bpm_step_spin.setMinimum(1)
        self._bpm_step_spin.setMaximum(10)
        self._bpm_step_spin.setToolTip(
            "Step between BPM positions (e.g., 3 means 9, 12, 15, 18, ...)"
        )
        bpm_layout.addRow("BPM Step:", self._bpm_step_spin)

        # Max Start BPM Position
        self._bpm_start_max_pos_spin = QtWidgets.QSpinBox()
        self._bpm_start_max_pos_spin.setMinimum(1)
        self._bpm_start_max_pos_spin.setMaximum(50)
        self._bpm_start_max_pos_spin.setToolTip(
            "Maximum position value for start BPMs\n"
            "E.g., 35 means BPMs go from start position to 35 in steps"
        )
        bpm_layout.addRow("Start Max Position:", self._bpm_start_max_pos_spin)

        # Max End BPM Position
        self._bpm_end_max_pos_spin = QtWidgets.QSpinBox()
        self._bpm_end_max_pos_spin.setMinimum(1)
        self._bpm_end_max_pos_spin.setMaximum(50)
        self._bpm_end_max_pos_spin.setToolTip(
            "Maximum position value for end BPMs\n"
            "E.g., 34 means BPMs go from start position to 34 in steps"
        )
        bpm_layout.addRow("End Max Position:", self._bpm_end_max_pos_spin)

        # Info label showing what BPMs will be generated
        self._bpm_preview_label = QtWidgets.QLabel("")
        self._bpm_preview_label.setWordWrap(True)
        self._bpm_preview_label.setStyleSheet(
            f"color: {colors.SECONDARY_TEXT_DARK}; font-size: 10px; padding: 5px;"
        )
        bpm_layout.addRow("Preview:", self._bpm_preview_label)

        bpm_group.setLayout(bpm_layout)
        layout.addWidget(bpm_group)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        cancel_button = DefaultButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        ok_button = DefaultButton("OK")
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)

        layout.addLayout(button_layout)

        # Connect signals
        self._start_bpm_combo.currentTextChanged.connect(self._update_start_s)
        self._end_bpm_combo.currentTextChanged.connect(self._update_end_s)
        self._start_slider.valueChanged.connect(self._update_start_bpm_from_slider)
        self._end_slider.valueChanged.connect(self._update_end_bpm_from_slider)

        # Connect BPM parameter changes to preview update
        self._start_bpm_combo.currentTextChanged.connect(self._update_bpm_preview)
        self._bpm_step_spin.valueChanged.connect(self._update_bpm_preview)
        self._bpm_start_max_pos_spin.valueChanged.connect(self._update_bpm_preview)
        self._bpm_end_max_pos_spin.valueChanged.connect(self._update_bpm_preview)

    def _load_data(self):
        """Load data from the arc configuration."""
        self._name_edit.setText(self._arc_config.name)

        if self._arc_config.magnet_range_start_bpm:
            index = self._start_bpm_combo.findText(self._arc_config.magnet_range_start_bpm)
            if index >= 0:
                self._start_bpm_combo.setCurrentIndex(index)
            else:
                self._start_bpm_combo.setCurrentText(self._arc_config.magnet_range_start_bpm)

        if self._arc_config.magnet_range_end_bpm:
            index = self._end_bpm_combo.findText(self._arc_config.magnet_range_end_bpm)
            if index >= 0:
                self._end_bpm_combo.setCurrentIndex(index)
            else:
                self._end_bpm_combo.setCurrentText(self._arc_config.magnet_range_end_bpm)

        self._bpm_step_spin.setValue(self._arc_config.bpm_step)
        self._bpm_start_max_pos_spin.setValue(self._arc_config.bpm_start_max_position)
        self._bpm_end_max_pos_spin.setValue(self._arc_config.bpm_end_max_position)

        self._update_start_s()
        self._update_end_s()
        self._update_bpm_preview()

    def _set_bpm_s_label(self, bpm_name: str, label: QtWidgets.QLabel):
        """Set a label to the S position for a BPM name."""
        s_position = self._bpm_lookup.get(bpm_name)
        if s_position is None:
            label.setText("Unknown")
            return
        label.setText(f"{s_position:.2f}")

    def _update_start_s(self, bpm_name: str | None = None):
        """Update the start S position label based on selected BPM."""
        self._set_bpm_s_label(bpm_name or self._start_bpm_combo.currentText(), self._start_s_label)

    def _update_end_s(self, bpm_name: str | None = None):
        """Update the end S position label based on selected BPM."""
        self._set_bpm_s_label(bpm_name or self._end_bpm_combo.currentText(), self._end_s_label)

    def _update_bpm_from_slider(self, value: int, target_combo: QtWidgets.QComboBox):
        """Update BPM combo based on slider position."""
        if not self._bpms or self._max_bpm_s <= 0.0:
            return

        target_s = (value / 1000.0) * self._max_bpm_s
        closest_bpm = min(self._bpms, key=lambda bpm: abs(bpm.s_position - target_s))
        target_combo.setCurrentText(closest_bpm.name)

    def _update_start_bpm_from_slider(self, value: int):
        """Update start BPM combo based on slider position."""
        self._update_bpm_from_slider(value, self._start_bpm_combo)

    def _update_end_bpm_from_slider(self, value: int):
        """Update end BPM combo based on slider position."""
        self._update_bpm_from_slider(value, self._end_bpm_combo)

    def _extract_bpm_position(self, bpm_name: str) -> int:
        """Extract the position number from BPM name (e.g., 'BPM.9R1.B1' -> 9)."""
        match = re.search(r"BPM\.(\d+)[RL]", bpm_name)
        if match:
            return int(match.group(1))
        return 9  # Default

    def _update_bpm_preview(self):
        """Update the BPM preview showing what will be generated."""
        start_bpm = self._start_bpm_combo.currentText()
        step = self._bpm_step_spin.value()
        start_max = self._bpm_start_max_pos_spin.value()
        end_max = self._bpm_end_max_pos_spin.value()

        # Extract start position from BPM name
        start_pos = self._extract_bpm_position(start_bpm)

        # Generate example positions
        start_positions = list(range(start_pos, start_max + 1, step))
        end_positions = list(range(start_pos, end_max + 1, step))

        # Format preview
        start_str = ", ".join(str(p) for p in start_positions[:5])
        if len(start_positions) > 5:
            start_str += f", ... ({len(start_positions)} total)"

        end_str = ", ".join(str(p) for p in end_positions[:5])
        if len(end_positions) > 5:
            end_str += f", ... ({len(end_positions)} total)"

        preview = f"Start BPMs: {start_str}\nEnd BPMs: {end_str}"
        self._bpm_preview_label.setText(preview)

    def get_arc_config(self) -> ArcConfigData:
        """Get the configured arc data."""
        start_bpm_name = self._start_bpm_combo.currentText()
        end_bpm_name = self._end_bpm_combo.currentText()

        return ArcConfigData(
            name=self._name_edit.text(),
            magnet_range_start_bpm=start_bpm_name,
            magnet_range_end_bpm=end_bpm_name,
            magnet_range_start_s=self._bpm_lookup.get(start_bpm_name, 0.0),
            magnet_range_end_s=self._bpm_lookup.get(end_bpm_name, 0.0),
            bpm_step=self._bpm_step_spin.value(),
            bpm_start_max_position=self._bpm_start_max_pos_spin.value(),
            bpm_end_max_position=self._bpm_end_max_pos_spin.value(),
        )
