"""
Defaults for DPP Optimisation
------------------------------

Default values and configurations for the DPP optimisation GUI.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_KNOB_FILES_SUMMARY_TEXT = (
    "No knob files downloaded yet.\n"
    "Run Step 1 to fetch knobs from LSA and inspect counts + file locations."
)
DEFAULT_DATAFILE_INFO_TEXT = (
    "Creates the optimisation datafile from selected measurements.\n"
    "No run has been started yet."
)
DEFAULT_OPTIMISATION_INFO_TEXT = (
    "Runs optimisation across configured arcs.\n"
    "No run has been started yet."
)
DEFAULT_ANALYSIS_SUMMARY_TEXT = (
    "No analysis directory selected.\n"
    "Select analysis first, then adjust measurement files."
)
DEFAULT_ARC_INFO_TEXT = "No arc selected"


@dataclass
class ArcConfig:
    """Configuration for a single arc."""
    name: str
    magnet_range_start_bpm: str
    magnet_range_end_bpm: str
    bpm_step: int = 3  # Step between BPMs (e.g., 9, 12, 15, ...)
    bpm_start_max_position: int = 35  # Maximum position for start BPMs
    bpm_end_max_position: int = 34  # Maximum position for end BPMs


@dataclass
class OptimiserConfig:
    """Configuration for the optimizer."""
    max_epochs: int = 1000
    warmup_epochs: int = 3
    warmup_lr_start: float = 5e-7
    max_lr: float = 1e0
    min_lr: float = 1e0
    gradient_converged_value: float = 1e-6
    optimiser_type: str = "lbfgs"


@dataclass
class SimulationConfig:
    """Configuration for the simulation (constant)."""
    tracks_per_worker: int = 1
    num_batches: int = 1
    num_workers: int = 1
    optimise_energy: bool = True
    use_fixed_bpm: bool = False


@dataclass
class OptimisationRangeConfig:
    """Container matching optimise_ranges range_config interface."""

    magnet_ranges: list[str]
    bpm_starts: list[list[str]]
    bpm_end_points: list[list[str]]


def get_default_beam1_arcs() -> list[ArcConfig]:
    """Get default arc configurations for Beam 1."""
    return [
        ArcConfig(
            name=f"Arc {i}",
            magnet_range_start_bpm=f"BPM.9R{i}.B1",
            magnet_range_end_bpm=f"BPM.9L{i % 8 + 1}.B1",
            bpm_step=5,
            bpm_start_max_position=35,
            bpm_end_max_position=34,
        )
        for i in range(1, 9)
    ]


def get_default_beam2_arcs() -> list[ArcConfig]:
    """Get default arc configurations for Beam 2."""
    return [
        ArcConfig(
            name=f"Arc {i}",
            magnet_range_start_bpm=f"BPM.9L{9-i}.B2",
            magnet_range_end_bpm=f"BPM.9R{(9-i-2) % 8 + 1}.B2",
            bpm_step=5,
            bpm_start_max_position=35,
            bpm_end_max_position=34,
        )
        for i in range(1, 9)
    ]


def generate_arc_bpm_lists(
    start_bpm_name: str,
    end_bpm_name: str,
    sector: int,
    beam: int,
    bpm_step: int,
    start_max_position: int,
    end_max_position: int,
) -> tuple[list[str], list[str]]:
    """
    Generate BPM lists for start and end points based on configuration.

    Args:
        start_bpm_name: Starting BPM name (e.g., "BPM.9R1.B1")
        end_bpm_name: Ending BPM name (e.g., "BPM.9L2.B1")
        sector: Sector number (1-8)
        beam: Beam number (1 or 2)
        bpm_step: Step between BPM positions (e.g., 3)
        start_max_position: Maximum position for start BPMs (e.g., 35)
        end_max_position: Maximum position for end BPMs (e.g., 34)

    Returns:
        Tuple of (start_bpm_list, end_bpm_list)

    Example for Beam 1:
        - start_bpms: ["BPM.9R1.B1", "BPM.12R1.B1", "BPM.15R1.B1", ...]
        - end_bpms: ["BPM.9L2.B1", "BPM.12L2.B1", "BPM.15L2.B1", ...]
    """
    # Extract start position from start BPM name
    match = re.search(r"BPM\.(\d+)[RL]", start_bpm_name)
    start_pos = int(match.group(1)) if match else 9

    # Determine orientation (R or L) from BPM names
    start_orientation = "R" if "R" in start_bpm_name else "L"
    end_orientation = "R" if "R" in end_bpm_name else "L"

    # Extract sectors
    start_match = re.search(r"[RL](\d+)\.B", start_bpm_name)
    end_match = re.search(r"[RL](\d+)\.B", end_bpm_name)
    start_sector = int(start_match.group(1)) if start_match else sector
    end_sector = int(end_match.group(1)) if end_match else (sector % 8 + 1)

    beam_suffix = f"B{beam}"

    # Generate start BPMs
    start_bpms = [
        f"BPM.{pos}{start_orientation}{start_sector}.{beam_suffix}"
        for pos in range(start_pos, start_max_position + 1, bpm_step)
    ]

    # Generate end BPMs
    end_bpms = [
        f"BPM.{pos}{end_orientation}{end_sector}.{beam_suffix}"
        for pos in range(start_pos, end_max_position + 1, bpm_step)
    ]

    return start_bpms, end_bpms


def build_optimisation_range_config(
    arcs: list[dict[str, object]],
    beam: int,
) -> OptimisationRangeConfig:
    """Build optimise_ranges-compatible arc configuration from arc dictionaries."""
    magnet_ranges: list[str] = []
    bpm_starts: list[list[str]] = []
    bpm_end_points: list[list[str]] = []

    for idx, arc in enumerate(arcs, start=1):
        start_bpm = str(arc["magnet_range_start_bpm"])
        end_bpm = str(arc["magnet_range_end_bpm"])
        magnet_ranges.append(f"{start_bpm}/{end_bpm}")
        start_bpms, end_bpms = generate_arc_bpm_lists(
            start_bpm_name=start_bpm,
            end_bpm_name=end_bpm,
            sector=idx,
            beam=beam,
            bpm_step=int(arc["bpm_step"]),
            start_max_position=int(arc["bpm_start_max_position"]),
            end_max_position=int(arc["bpm_end_max_position"]),
        )
        bpm_starts.append(start_bpms)
        bpm_end_points.append(end_bpms)

    return OptimisationRangeConfig(
        magnet_ranges=magnet_ranges,
        bpm_starts=bpm_starts,
        bpm_end_points=bpm_end_points,
    )
