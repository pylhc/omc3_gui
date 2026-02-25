"""
Optimizer Settings Dialog
--------------------------

Dialog for configuring optimizer settings (advanced users only).
"""
from __future__ import annotations

import logging
from typing import Optional

from qtpy import QtWidgets

from omc3_gui.dpp_optimisation.defaults import OptimiserConfig
from omc3_gui.ui_components import colors
from omc3_gui.ui_components.message_boxes import show_confirmation_dialog
from omc3_gui.ui_components.widgets import DefaultButton

LOGGER = logging.getLogger(__name__)


class OptimizerSettingsDialog(QtWidgets.QDialog):
    """Dialog for configuring optimizer settings."""

    def __init__(self, config: Optional[OptimiserConfig] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Optimizer Settings (Advanced)")
        self.setModal(True)
        self.resize(500, 400)

        self._config = config or OptimiserConfig()
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        """Build the user interface."""
        layout = QtWidgets.QVBoxLayout(self)

        # Warning label
        warning_label = QtWidgets.QLabel(
            "⚠️ ADVANCED USERS ONLY ⚠️\n\n"
            "These settings control the optimisation algorithm.\n"
            "Incorrect values may cause the optimisation to fail or produce poor results."
        )
        warning_label.setWordWrap(True)
        warning_label.setStyleSheet(
            f"color: {colors.RED_DARK}; font-weight: bold; padding: 10px;"
        )
        layout.addWidget(warning_label)

        # Settings Form
        form_layout = QtWidgets.QFormLayout()

        # Max Epochs
        self._max_epochs_spin = QtWidgets.QSpinBox()
        self._max_epochs_spin.setMinimum(1)
        self._max_epochs_spin.setMaximum(10000)
        self._max_epochs_spin.setToolTip("Maximum number of optimisation iterations")
        form_layout.addRow("Max Epochs:", self._max_epochs_spin)

        # Warmup Epochs
        self._warmup_epochs_spin = QtWidgets.QSpinBox()
        self._warmup_epochs_spin.setMinimum(0)
        self._warmup_epochs_spin.setMaximum(100)
        self._warmup_epochs_spin.setToolTip("Number of warmup iterations with gradually increasing learning rate")
        form_layout.addRow("Warmup Epochs:", self._warmup_epochs_spin)

        # Warmup LR Start
        self._warmup_lr_start = QtWidgets.QLineEdit()
        self._warmup_lr_start.setToolTip("Initial learning rate during warmup (scientific notation: 5e-7)")
        form_layout.addRow("Warmup LR Start:", self._warmup_lr_start)

        # Max LR
        self._max_lr = QtWidgets.QLineEdit()
        self._max_lr.setToolTip("Maximum learning rate (scientific notation: 1e0)")
        form_layout.addRow("Max Learning Rate:", self._max_lr)

        # Min LR
        self._min_lr = QtWidgets.QLineEdit()
        self._min_lr.setToolTip("Minimum learning rate (scientific notation: 1e0)")
        form_layout.addRow("Min Learning Rate:", self._min_lr)

        # Gradient Converged Value
        self._gradient_converged = QtWidgets.QLineEdit()
        self._gradient_converged.setToolTip("Convergence threshold for gradient norm (scientific notation: 1e-6)")
        form_layout.addRow("Gradient Converged:", self._gradient_converged)

        # Optimizer Type
        self._optimizer_type_combo = QtWidgets.QComboBox()
        self._optimizer_type_combo.addItems(["lbfgs", "adam", "sgd"])
        self._optimizer_type_combo.setToolTip("Type of optimizer algorithm to use")
        form_layout.addRow("Optimizer Type:", self._optimizer_type_combo)

        layout.addLayout(form_layout)

        # Add a separator
        layout.addWidget(QtWidgets.QLabel())

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()

        reset_button = DefaultButton("Reset to Defaults")
        reset_button.clicked.connect(self._reset_to_defaults)
        button_layout.addWidget(reset_button)

        button_layout.addStretch()

        cancel_button = DefaultButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        ok_button = DefaultButton("OK")
        ok_button.clicked.connect(self._on_ok_clicked)
        button_layout.addWidget(ok_button)

        layout.addLayout(button_layout)

    def _load_data(self):
        """Load data from the configuration."""
        self._max_epochs_spin.setValue(self._config.max_epochs)
        self._warmup_epochs_spin.setValue(self._config.warmup_epochs)
        self._warmup_lr_start.setText(str(self._config.warmup_lr_start))
        self._max_lr.setText(str(self._config.max_lr))
        self._min_lr.setText(str(self._config.min_lr))
        self._gradient_converged.setText(str(self._config.gradient_converged_value))

        index = self._optimizer_type_combo.findText(self._config.optimiser_type)
        if index >= 0:
            self._optimizer_type_combo.setCurrentIndex(index)

    def _reset_to_defaults(self):
        """Reset all settings to default values."""
        self._config = OptimiserConfig()
        self._load_data()

    def _on_ok_clicked(self):
        """Handle OK button click with confirmation."""
        # Show confirmation dialog
        result = show_confirmation_dialog(
            question="Are you sure you want to apply these optimizer settings?\n\n"
                     "Incorrect settings may cause optimisation to fail.",
            title="Confirm Settings",
            parent=self,
        )

        if result:
            self.accept()

    def get_config(self) -> OptimiserConfig:
        """Get the configured optimizer settings."""
        try:
            return OptimiserConfig(
                max_epochs=self._max_epochs_spin.value(),
                warmup_epochs=self._warmup_epochs_spin.value(),
                warmup_lr_start=float(self._warmup_lr_start.text()),
                max_lr=float(self._max_lr.text()),
                min_lr=float(self._min_lr.text()),
                gradient_converged_value=float(self._gradient_converged.text()),
                optimiser_type=self._optimizer_type_combo.currentText(),
            )
        except ValueError as e:
            LOGGER.error(f"Error parsing optimizer config: {e}")
            # Return current config if parsing fails
            return self._config
