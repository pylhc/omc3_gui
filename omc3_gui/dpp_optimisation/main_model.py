"""
Main Model for DPP Optimisation
--------------------------------

This module contains the data models for the DPP optimisation GUI.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from qtpy import QtCore
from qtpy.QtCore import Qt

ItemDataRole = Qt.ItemDataRole

LOGGER = logging.getLogger(__name__)


@dataclass
class BpmInfo:
    """Information about a BPM."""
    name: str
    s_position: float


@dataclass
class ModelInfo:
    """Information extracted from the model directory."""
    model_dir: Path
    sequence_file: Optional[Path] = None
    beam: Optional[int] = None
    beam_energy: Optional[float] = None
    bpms: list[BpmInfo] = field(default_factory=list)

    def is_valid(self) -> bool:
        """Check if the model info is valid and complete."""
        return (
            self.model_dir is not None
            and self.sequence_file is not None
            and self.beam is not None
            and len(self.bpms) > 0
        )


@dataclass
class ArcConfigData:
    """Configuration data for a single arc."""
    name: str
    magnet_range_start_bpm: str
    magnet_range_end_bpm: str
    magnet_range_start_s: float = 0.0
    magnet_range_end_s: float = 0.0
    bpm_step: int = 3
    bpm_start_max_position: int = 35
    bpm_end_max_position: int = 34


class ArcListModel(QtCore.QAbstractListModel):
    """List model for arc configurations."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._arcs: list[ArcConfigData] = []

    def data(self, index: QtCore.QModelIndex, role: int = ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        arc = self._arcs[index.row()]

        if role == ItemDataRole.DisplayRole:
            return arc.name

        if role == ItemDataRole.ToolTipRole:
            return f"{arc.name}: {arc.magnet_range_start_bpm} to {arc.magnet_range_end_bpm}"

        if role == ItemDataRole.UserRole:
            return arc

        return None

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return len(self._arcs)

    def add_arc(self, arc: ArcConfigData):
        """Add an arc to the model."""
        self.beginInsertRows(QtCore.QModelIndex(), len(self._arcs), len(self._arcs))
        self._arcs.append(arc)
        self.endInsertRows()

    def remove_arc(self, row: int):
        """Remove an arc from the model."""
        if 0 <= row < len(self._arcs):
            self.beginRemoveRows(QtCore.QModelIndex(), row, row)
            del self._arcs[row]
            self.endRemoveRows()

    def update_arc(self, row: int, arc: ArcConfigData):
        """Update an arc in the model."""
        if 0 <= row < len(self._arcs):
            self._arcs[row] = arc
            index = self.index(row, 0)
            self.dataChanged.emit(index, index)

    def get_arc(self, row: int) -> Optional[ArcConfigData]:
        """Get an arc by row number."""
        if 0 <= row < len(self._arcs):
            return self._arcs[row]
        return None

    def get_all_arcs(self) -> list[ArcConfigData]:
        """Get all arcs."""
        return self._arcs.copy()

    def clear(self):
        """Clear all arcs."""
        self.beginResetModel()
        self._arcs.clear()
        self.endResetModel()

    def load_defaults(self, beam: int, bpms: Optional[list[BpmInfo]] = None):
        """Load default arc configurations for the given beam."""
        from omc3_gui.dpp_optimisation.defaults import (
            get_default_beam1_arcs,
            get_default_beam2_arcs,
        )

        bpm_s_positions = {}
        if bpms:
            bpm_s_positions = {bpm.name: bpm.s_position for bpm in bpms}

        self.beginResetModel()
        self._arcs.clear()

        if beam == 1:
            defaults = get_default_beam1_arcs()
        elif beam == 2:
            defaults = get_default_beam2_arcs()
        else:
            defaults = []

        for arc_default in defaults:
            start_s = bpm_s_positions.get(arc_default.magnet_range_start_bpm, 0.0)
            end_s = bpm_s_positions.get(arc_default.magnet_range_end_bpm, 0.0)
            self._arcs.append(
                ArcConfigData(
                    name=arc_default.name,
                    magnet_range_start_bpm=arc_default.magnet_range_start_bpm,
                    magnet_range_end_bpm=arc_default.magnet_range_end_bpm,
                    magnet_range_start_s=start_s,
                    magnet_range_end_s=end_s,
                    bpm_step=arc_default.bpm_step,
                    bpm_start_max_position=arc_default.bpm_start_max_position,
                    bpm_end_max_position=arc_default.bpm_end_max_position,
                )
            )

        self.endResetModel()


class MeasurementFileListModel(QtCore.QAbstractListModel):
    """List model for measurement files."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._files: list[Path] = []

    def data(self, index: QtCore.QModelIndex, role: int = ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        file_path = self._files[index.row()]

        if role == ItemDataRole.DisplayRole:
            return file_path.name

        if role == ItemDataRole.ToolTipRole:
            return str(file_path)

        if role == ItemDataRole.UserRole:
            return file_path

        return None

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return len(self._files)

    def add_files(self, files: list[Path]):
        """Add files to the model."""
        for file_path in files:
            if file_path not in self._files:
                self.beginInsertRows(
                    QtCore.QModelIndex(), len(self._files), len(self._files)
                )
                self._files.append(file_path)
                self.endInsertRows()

    def add_folders(self, folders: list[Path]):
        """Add all files from the given folders to the model."""
        for folder in folders:
            if folder.is_dir():
                files_in_folder = list(folder.glob("*.sdds"))
                self.add_files(files_in_folder)

    def remove_file(self, row: int):
        """Remove a file from the model."""
        if 0 <= row < len(self._files):
            self.beginRemoveRows(QtCore.QModelIndex(), row, row)
            del self._files[row]
            self.endRemoveRows()

    def get_all_files(self) -> list[Path]:
        """Get all files."""
        return self._files.copy()

    def clear(self):
        """Clear all files."""
        self.beginResetModel()
        self._files.clear()
        self.endResetModel()
