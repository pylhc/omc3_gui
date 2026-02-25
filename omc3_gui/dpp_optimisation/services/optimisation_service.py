from __future__ import annotations

import dataclasses
import logging
import shlex
import shutil
import subprocess
import threading
import time
from collections.abc import Iterable
from math import isfinite
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, cast

import pandas as pd
from qtpy.QtCore import Slot
from qtpy.QtWidgets import QApplication

from omc3_gui.dpp_optimisation.defaults import (
    build_optimisation_range_config as build_range_config_from_arcs,
)
from omc3_gui.dpp_optimisation.services import remote_jobs, ssh_service
from omc3_gui.ui_components.message_boxes import (
    show_confirmation_dialog,
    show_error_dialog,
    show_info_dialog,
)

if TYPE_CHECKING:
    from omc3_gui.dpp_optimisation.main_controller import DppOptimisationController

LOGGER = logging.getLogger(__name__)


def _payload_mapping(data: object) -> Mapping[str, object]:
    if isinstance(data, Mapping):
        parsed: dict[str, object] = {}
        for key, value in data.items():
            if not isinstance(key, str):
                raise RuntimeError(
                    f"Invalid optimisation payload key type: {type(key).__name__}"
                )
            parsed[key] = value
        return parsed
    raise RuntimeError(f"Invalid optimisation payload type: {type(data).__name__}")


def _float_input(value: object, *, field_name: str) -> int | float | str | bytes:
    if isinstance(value, (int, float, str, bytes)):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    raise TypeError(f"Field '{field_name}' is not float-convertible: {type(value).__name__}")


def _payload_list_of_floats(
    payload: Mapping[str, object],
    *,
    keys: tuple[str, ...],
    default: list[float] | None = None,
) -> list[float]:
    for key in keys:
        raw = payload.get(key)
        if raw is None:
            continue
        if isinstance(raw, (str, bytes, Mapping)):
            raise RuntimeError(f"Optimisation payload field '{key}' must be a list, got string.")
        if not isinstance(raw, Iterable):
            raise RuntimeError(f"Optimisation payload field '{key}' is not iterable.")
        try:
            return [float(_float_input(value, field_name=key)) for value in raw]
        except (ValueError, OverflowError) as exc:
            raise RuntimeError(
                f"Optimisation payload field '{key}' contains non-numeric values."
            ) from exc
        except TypeError as exc:
            raise RuntimeError(str(exc)) from exc
    return [] if default is None else list(default)


def _require_float(data: Mapping[str, object], key: str) -> float:
    try:
        return float(_float_input(data[key], field_name=key))
    except KeyError as exc:
        raise RuntimeError(f"Missing optimisation result key: {key}") from exc
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Invalid optimisation result key '{key}' (expected float)") from exc


def _optional_float(data: Mapping[str, object], key: str) -> float | None:
    value = data.get(key)
    if value is None:
        return None
    try:
        return float(_float_input(value, field_name=key))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Invalid optimisation result key '{key}' (expected float or null)") from exc


def _require_path(data: Mapping[str, object], key: str) -> Path:
    try:
        return Path(str(data[key]))
    except KeyError as exc:
        raise RuntimeError(f"Missing optimisation result key: {key}") from exc


def _require_str(data: Mapping[str, object], key: str) -> str:
    try:
        return str(data[key])
    except KeyError as exc:
        raise RuntimeError(f"Missing optimisation result key: {key}") from exc


def _format_standard_number(value: float | None) -> str:
    """Format numbers in scientific standard form for compact display."""
    if value is None:
        return "n/a"
    return f"{float(value):.6e}"


def _snapshot_results_for_tab(
    ctrl: DppOptimisationController,
    *,
    results_file: Path,
    origin_ctx,
) -> Path:
    """Copy results into a tab-scoped snapshot file to avoid cross-tab overwrites."""
    snapshot_dir: Path | None = None
    if origin_ctx.temp_work_dir is not None:
        snapshot_dir = Path(origin_ctx.temp_work_dir.name)
    elif (
        0 <= ctrl._active_tab_index < len(ctrl._optimisation_tabs)
        and ctrl._optimisation_tabs[ctrl._active_tab_index] is origin_ctx
    ):
        snapshot_dir = ctrl._get_temp_work_dir()

    if snapshot_dir is None:
        return results_file

    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / f"deltap_optimisation_results_{int(time.time() * 1000)}.txt"
    try:
        shutil.copy2(results_file, snapshot_path)
        return snapshot_path
    except OSError as exc:
        LOGGER.warning(
            "Failed to create tab-scoped results snapshot at %s: %s. Using original file %s.",
            snapshot_path,
            exc,
            results_file,
        )
        return results_file


def _results_file_candidates(ctrl: DppOptimisationController, filename: str) -> tuple[Path, list[Path]]:
    """Return preferred and fallback candidate paths for result output."""
    if ctrl._analysis_dir is None:
        raise RuntimeError("Analysis directory missing.")
    preferred_results_file = ctrl._analysis_dir / filename
    fallback_results_file = ctrl._get_temp_work_dir() / filename
    candidates = [preferred_results_file]
    if fallback_results_file != preferred_results_file:
        candidates.append(fallback_results_file)
    return preferred_results_file, candidates


def _write_deltap_results_content(
    path: Path,
    *,
    beam_energy: float,
    deltap_wrt_6800: list[float],
    uncertainties: list[float],
    fitted_deltap_wrt_model_energy: list[float],
    mean_wrt_6800: float | None,
    mean_fitted_wrt_model_energy: float | None,
    std_dev_wrt_6800: float,
    stderr_wrt_6800: float,
):
    """Write one complete delta-p result file."""
    with path.open("w") as file:
        file.write(f"# model_energy_reference_GeV\t{beam_energy}\n")
        file.write("# output_energy_reference_GeV\t6800.0\n")
        file.write(
            "range\t"
            "deltap_wrt_6800GeV\t"
            "uncertainty_of_fitted_deltap\t"
            f"fitted_deltap_wrt_model_energy_{beam_energy:.1f}GeV\n"
        )
        for idx, deltap in enumerate(deltap_wrt_6800, start=1):
            unc = uncertainties[idx - 1] if idx - 1 < len(uncertainties) else float("nan")
            fitted = (
                fitted_deltap_wrt_model_energy[idx - 1]
                if idx - 1 < len(fitted_deltap_wrt_model_energy)
                else float("nan")
            )
            file.write(f"arc{idx}\t{deltap}\t{unc}\t{fitted}\n")
        file.write(f"MeanDeltaP_wrt_6800GeV\t{mean_wrt_6800 if mean_wrt_6800 is not None else 'nan'}\t\t\n")
        file.write(
            "MeanFittedDeltaP_wrt_model_energy_"
            f"{beam_energy:.1f}GeV\t"
            f"{mean_fitted_wrt_model_energy if mean_fitted_wrt_model_energy is not None else 'nan'}\t\t\n"
        )
        file.write(f"StdDevDeltaP_wrt_6800GeV\t{std_dev_wrt_6800}\t\t\n")
        file.write(f"StdErrDeltaP_wrt_6800GeV\t{stderr_wrt_6800}\t\t\n")


def _write_results_file_with_fallback(
    ctrl: DppOptimisationController,
    *,
    beam_energy: float,
    deltap_wrt_6800: list[float],
    uncertainties: list[float],
    fitted_deltap_wrt_model_energy: list[float],
    mean_wrt_6800: float | None,
    mean_fitted_wrt_model_energy: float | None,
    std_dev_wrt_6800: float,
    stderr_wrt_6800: float,
) -> tuple[Path, str]:
    """Write results to analysis dir, then fallback to temp dir if needed."""
    preferred_results_file, candidate_paths = _results_file_candidates(
        ctrl,
        filename="deltap_optimisation_results.txt",
    )

    write_errors: list[str] = []
    results_file: Path | None = None
    for candidate in candidate_paths:
        try:
            candidate.parent.mkdir(parents=True, exist_ok=True)
            _write_deltap_results_content(
                candidate,
                beam_energy=beam_energy,
                deltap_wrt_6800=deltap_wrt_6800,
                uncertainties=uncertainties,
                fitted_deltap_wrt_model_energy=fitted_deltap_wrt_model_energy,
                mean_wrt_6800=mean_wrt_6800,
                mean_fitted_wrt_model_energy=mean_fitted_wrt_model_energy,
                std_dev_wrt_6800=std_dev_wrt_6800,
                stderr_wrt_6800=stderr_wrt_6800,
            )
            results_file = candidate
            break
        except OSError as exc:
            write_errors.append(f"{candidate}: {exc}")

    if results_file is None:
        raise RuntimeError("Failed to write optimisation results file.\n" + "\n".join(write_errors))

    if results_file == preferred_results_file:
        return results_file, ""

    fallback_warning = (
        f"WARNING: Could not write results to analysis directory ({preferred_results_file}). "
        f"Saved to temporary directory: {results_file}"
    )
    return results_file, fallback_warning


def build_optimisation_range_config(ctrl: DppOptimisationController, beam: int):
    """Create optimise_ranges-compatible range config from GUI arc settings."""
    arcs = [
        {
            "magnet_range_start_bpm": arc.magnet_range_start_bpm,
            "magnet_range_end_bpm": arc.magnet_range_end_bpm,
            "bpm_step": arc.bpm_step,
            "bpm_start_max_position": arc.bpm_start_max_position,
            "bpm_end_max_position": arc.bpm_end_max_position,
        }
        for arc in ctrl._arc_list_model.get_all_arcs()
    ]
    return build_range_config_from_arcs(
        arcs=arcs,
        beam=beam,
    )


def make_aba_config_objects(ctrl: DppOptimisationController):
    """Translate GUI config dataclasses to aba_optimiser config objects."""
    from aba_optimiser.config import (
        OptimiserConfig as AbaOptimiserConfig,
    )
    from aba_optimiser.config import (
        SimulationConfig as AbaSimulationConfig,
    )

    optimiser_values = dataclasses.asdict(ctrl._optimizer_config)
    simulation_values = dataclasses.asdict(ctrl._simulation_config)
    optimiser_fallbacks = {"expected_rel_error": 0.0}
    simulation_fallbacks = {"optimise_momenta": True, "optimise_correctors": False}
    optimiser_kwargs = cast(
        dict[str, Any],
        remote_jobs.build_config_kwargs(
            AbaOptimiserConfig,
            optimiser_values,
            optimiser_fallbacks,
        ),
    )
    simulation_kwargs = cast(
        dict[str, Any],
        remote_jobs.build_config_kwargs(
            AbaSimulationConfig,
            simulation_values,
            simulation_fallbacks,
        ),
    )
    optimiser_config = AbaOptimiserConfig(**optimiser_kwargs)
    simulation_config = AbaSimulationConfig(**simulation_kwargs)
    return optimiser_config, simulation_config


def weighted_mean(values: list[float], uncertainties: list[float]) -> float | None:
    """Compute weighted mean with 1/sigma^2 weights."""
    finite_pairs = [
        (value, unc)
        for value, unc in zip(values, uncertainties)
        if isfinite(value) and isfinite(unc) and unc > 0.0
    ]
    if not finite_pairs:
        return None
    weights = [1.0 / (unc * unc) for _, unc in finite_pairs]
    numerator = sum(value * weight for (value, _), weight in zip(finite_pairs, weights))
    denominator = sum(weights)
    if denominator <= 0.0:
        return None
    return numerator / denominator


def copy_file_to_remote(ctrl: DppOptimisationController, host: str, local_path: Path, remote_path: str):
    """Copy local file to remote path via SCP."""
    remote_parent = str(Path(remote_path).parent)
    mkdir_result = ctrl._run_ssh_command(host, f"mkdir -p {shlex.quote(remote_parent)}")
    if mkdir_result.returncode != 0:
        stderr = mkdir_result.stderr.strip() or mkdir_result.stdout.strip() or "Unknown mkdir error"
        raise RuntimeError(f"Failed creating remote directory on {host}: {stderr}")

    scp_result = subprocess.run(
        [
            "scp",
            "-o",
            "BatchMode=yes",
            "-o",
            f"ConnectTimeout={ctrl.SSH_CONNECT_TIMEOUT_SECONDS}",
            str(local_path),
            f"{host}:{remote_path}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if scp_result.returncode != 0:
        stderr = scp_result.stderr.strip() or scp_result.stdout.strip() or "Unknown scp error"
        raise RuntimeError(f"Failed copying {local_path} to {host}:{remote_path}: {stderr}")


def resolve_file_for_remote_optimisation(
    ctrl: DppOptimisationController,
    *,
    host: str,
    beam: int,
    local_path: Path | None,
    remote_path: str | None,
    default_filename: str,
) -> str:
    """Resolve remote path for optimisation input file, copying from local when needed."""
    remote_work_dir = ctrl._get_remote_work_dir(beam)
    default_remote = f"{remote_work_dir}/{default_filename}"

    if remote_path:
        if ctrl._remote_host == host:
            # Remote path was produced by this GUI flow for the same host.
            # Avoid repeated SSH existence probes here; remote execution will
            # fail with a concrete error if file is actually missing.
            return remote_path
        elif local_path is None or not local_path.exists():
            raise RuntimeError(
                f"Required file exists on different remote host only: {remote_path} (host={ctrl._remote_host})"
            )

    if local_path is None or not local_path.exists():
        raise RuntimeError(f"Required local file does not exist: {local_path}")

    copy_file_to_remote(ctrl, host, local_path, default_remote)
    return default_remote


def run_optimisation_locally(
    ctrl: DppOptimisationController,
    *,
    beam: int,
    energy: float,
    sequence_file: Path,
    magnet_knobs_file: Path,
    corrector_knobs_file: Path,
    measurement_file: Path,
    bad_bpms: list[str],
) -> dict[str, object]:
    """Run optimisation in local process."""
    payload = _build_optimisation_payload(
        ctrl=ctrl,
        beam=beam,
        energy=energy,
        sequence_file=sequence_file,
        magnet_knobs_file=magnet_knobs_file,
        corrector_knobs_file=corrector_knobs_file,
        measurement_file=measurement_file,
        bad_bpms=bad_bpms,
        source="local",
    )
    return remote_jobs.run_optimisation_job(payload)


def _build_optimisation_payload(
    *,
    ctrl: DppOptimisationController,
    beam: int,
    energy: float,
    sequence_file: Path | str,
    magnet_knobs_file: Path | str,
    corrector_knobs_file: Path | str,
    measurement_file: Path | str,
    bad_bpms: list[str],
    source: str,
) -> dict[str, object]:
    return {
        "beam": beam,
        "energy": float(energy),
        "sequence_file": str(sequence_file),
        "magnet_knobs_file": str(magnet_knobs_file),
        "corrector_knobs_file": str(corrector_knobs_file),
        "measurement_file": str(measurement_file),
        "bad_bpms": list(bad_bpms),
        "arcs": [
            {
                "name": arc.name,
                "magnet_range_start_bpm": arc.magnet_range_start_bpm,
                "magnet_range_end_bpm": arc.magnet_range_end_bpm,
                "bpm_step": int(arc.bpm_step),
                "bpm_start_max_position": int(arc.bpm_start_max_position),
                "bpm_end_max_position": int(arc.bpm_end_max_position),
            }
            for arc in ctrl._arc_list_model.get_all_arcs()
        ],
        "optimiser_config": dataclasses.asdict(ctrl._optimizer_config),
        "simulation_config": dataclasses.asdict(ctrl._simulation_config),
        "source": source,
    }


def run_optimisation_via_ssh(
    ctrl: DppOptimisationController,
    *,
    host: str,
    beam: int,
    energy: float,
    sequence_file: str,
    magnet_knobs_file: str,
    corrector_knobs_file: str,
    measurement_file: str,
    bad_bpms: list[str],
) -> dict[str, object]:
    """Run optimisation on remote host and return parsed payload."""
    payload = _build_optimisation_payload(
        ctrl=ctrl,
        beam=beam,
        energy=energy,
        sequence_file=sequence_file,
        magnet_knobs_file=magnet_knobs_file,
        corrector_knobs_file=corrector_knobs_file,
        measurement_file=measurement_file,
        bad_bpms=bad_bpms,
        source=f"remote:{host}",
    )
    return ssh_service.run_remote_json_job(
        ctrl,
        host=host,
        module="omc3_gui.dpp_optimisation.services.remote_jobs",
        function="run_optimisation_job",
        payload=payload,
        marker="OMC3_GUI_OPT_RESULT=",
    )


def check_required_files_exist(ctrl: DppOptimisationController) -> bool:
    """Check if all required files exist."""
    remote_host = ctrl._remote_host
    has_remote_artifacts = False

    if ctrl._remote_magnet_knobs_file:
        has_remote_artifacts = True
        magnet_knobs_exists = bool(remote_host)
    else:
        magnet_knobs_exists = ctrl._get_magnet_knobs_file().exists()

    if ctrl._remote_corrector_knobs_file:
        has_remote_artifacts = True
        corrector_knobs_exists = bool(remote_host)
    else:
        corrector_knobs_exists = ctrl._get_corrector_knobs_file().exists()

    if ctrl._remote_measurement_datafile:
        has_remote_artifacts = True
        datafile_exists = bool(remote_host)
    else:
        datafile_exists = ctrl._measurement_datafile is not None and ctrl._measurement_datafile.exists()

    if has_remote_artifacts and not remote_host:
        return False

    return (
        magnet_knobs_exists
        and corrector_knobs_exists
        and ctrl._datafile_created
        and datafile_exists
    )


@Slot()
def on_run_optimisation(ctrl: DppOptimisationController):
    """Handle run optimisation button click."""
    if ctrl._active_tab_index < 0 or ctrl._active_tab_index >= len(ctrl._optimisation_tabs):
        return
    origin_ctx = ctrl._optimisation_tabs[ctrl._active_tab_index]

    def is_origin_tab_active() -> bool:
        return (
            0 <= ctrl._active_tab_index < len(ctrl._optimisation_tabs)
            and ctrl._optimisation_tabs[ctrl._active_tab_index] is origin_ctx
        )

    def origin_ctx_exists() -> bool:
        return any(ctx is origin_ctx for ctx in ctrl._optimisation_tabs)

    running_tasks = ctrl._get_running_processes_count()
    if running_tasks > 0:
        show_error_dialog(
            title="Task In Progress",
            message=(
                "Another operation is currently running.\n\n"
                "Please wait for it to finish before starting optimisation."
            ),
            parent=ctrl._view,
        )
        return

    if getattr(ctrl, "_optimisation_running", False):
        show_error_dialog(
            title="Optimisation In Progress",
            message="An optimisation is already running. Only 'View Results' is available.",
            parent=ctrl._view,
        )
        return

    if not ctrl._validate_for_optimisation():
        return

    result = show_confirmation_dialog(
        title="Run Optimisation",
        question=f"This will run the optimisation for all {len(ctrl._arc_list_model.get_all_arcs())} arcs.\n\n"
        "Continue?",
        parent=ctrl._view,
    )

    if not result:
        return

    ctrl._optimisation_running = True
    ctrl._register_running_processes(1)
    ctrl._update_action_buttons()
    ctrl._view.update_bottom_progress(
        text=ctrl._format_running_processes_text("Running optimisation..."),
        value=0,
        maximum=1,
        indeterminate=True,
        visible=True,
    )

    worker_result: dict[str, object] = {}
    worker_error: Exception | None = None

    def run_worker():
        nonlocal worker_error
        try:
            ctrl._raise_if_interrupted()
            LOGGER.warning("Optimisation start: running preflight checks.")
            files_exist = check_required_files_exist(ctrl)
            if not files_exist:
                raise RuntimeError(
                    "Required optimisation inputs are missing. "
                    "Please run Download Knobs and Create Datafile first."
                )
            _, beam, sequence_file, beam_energy = ctrl._require_loaded_model_context()
            local_magnet_knobs_file = ctrl._get_magnet_knobs_file()
            local_corrector_knobs_file = ctrl._get_corrector_knobs_file()
            local_measurement_datafile = ctrl._measurement_datafile
            magnet_knobs_path_for_info = str(local_magnet_knobs_file.resolve())
            corrector_knobs_path_for_info = str(local_corrector_knobs_file.resolve())

            has_remote_artifacts = any(
                (
                    ctrl._remote_magnet_knobs_file,
                    ctrl._remote_corrector_knobs_file,
                    ctrl._remote_measurement_datafile,
                )
            )
            available, host, message = ctrl._is_remote_server_available_for_beam(beam)
            ctrl._raise_if_interrupted()

            if has_remote_artifacts and not available:
                has_local_fallback = (
                    local_magnet_knobs_file.exists()
                    and local_corrector_knobs_file.exists()
                    and local_measurement_datafile is not None
                    and local_measurement_datafile.exists()
                )
                if not has_local_fallback:
                    raise RuntimeError(
                        f"Remote server {host} unavailable ({message}) and no complete local fallback artifacts found."
                    )

            if has_remote_artifacts and available:
                LOGGER.warning("Optimisation execution path: remote (%s).", host)
                remote_sequence_file = ctrl._resolve_sequence_file_for_ssh(host, beam, sequence_file)
                remote_magnet_knobs_file = resolve_file_for_remote_optimisation(
                    ctrl,
                    host=host,
                    beam=beam,
                    local_path=local_magnet_knobs_file if local_magnet_knobs_file.exists() else None,
                    remote_path=ctrl._remote_magnet_knobs_file,
                    default_filename=ctrl.MAGNET_KNOBS_FILENAME,
                )
                remote_corrector_knobs_file = resolve_file_for_remote_optimisation(
                    ctrl,
                    host=host,
                    beam=beam,
                    local_path=(
                        local_corrector_knobs_file if local_corrector_knobs_file.exists() else None
                    ),
                    remote_path=ctrl._remote_corrector_knobs_file,
                    default_filename=ctrl.CORRECTOR_KNOBS_FILENAME,
                )
                remote_measurement_file = resolve_file_for_remote_optimisation(
                    ctrl,
                    host=host,
                    beam=beam,
                    local_path=(
                        local_measurement_datafile
                        if (local_measurement_datafile is not None and local_measurement_datafile.exists())
                        else None
                    ),
                    remote_path=ctrl._remote_measurement_datafile,
                    default_filename=ctrl.MEASUREMENT_DATAFILE_FILENAME,
                )
                magnet_knobs_path_for_info = f"{remote_magnet_knobs_file} [remote:{host}]"
                corrector_knobs_path_for_info = f"{remote_corrector_knobs_file} [remote:{host}]"
                result_payload = run_optimisation_via_ssh(
                    ctrl,
                    host=host,
                    beam=beam,
                    energy=beam_energy,
                    sequence_file=remote_sequence_file,
                    magnet_knobs_file=remote_magnet_knobs_file,
                    corrector_knobs_file=remote_corrector_knobs_file,
                    measurement_file=remote_measurement_file,
                    bad_bpms=ctrl._bad_bpms,
                )
            else:
                LOGGER.warning("Optimisation execution path: local.")
                ctrl._raise_if_interrupted()
                if local_measurement_datafile is None or not local_measurement_datafile.exists():
                    raise RuntimeError("Measurement datafile missing for local optimisation.")
                if not local_magnet_knobs_file.exists():
                    raise RuntimeError("Magnet knobs file missing for local optimisation.")
                if not local_corrector_knobs_file.exists():
                    raise RuntimeError("Corrector knobs file missing for local optimisation.")

                magnet_knobs_path_for_info = str(local_magnet_knobs_file.resolve())
                corrector_knobs_path_for_info = str(local_corrector_knobs_file.resolve())
                result_payload = run_optimisation_locally(
                    ctrl,
                    beam=beam,
                    energy=beam_energy,
                    sequence_file=sequence_file,
                    magnet_knobs_file=local_magnet_knobs_file,
                    corrector_knobs_file=local_corrector_knobs_file,
                    measurement_file=local_measurement_datafile,
                    bad_bpms=ctrl._bad_bpms,
                )
            ctrl._raise_if_interrupted()

            result_payload = _payload_mapping(result_payload)
            deltap_wrt_6800 = _payload_list_of_floats(
                result_payload,
                keys=("deltap", "deltap_wrt_6800", "delta_p"),
            )
            uncertainties = _payload_list_of_floats(
                result_payload,
                keys=("uncertainties", "sigma", "errors"),
                default=[1.0] * len(deltap_wrt_6800),
            )
            fitted_deltap_wrt_model_energy = _payload_list_of_floats(
                result_payload,
                keys=("fitted_deltaps", "fitted_deltap_wrt_model_energy", "fitted_deltap"),
            )
            if not deltap_wrt_6800:
                raise RuntimeError("Optimisation completed but returned no results.")

            mean = weighted_mean(deltap_wrt_6800, uncertainties)
            mean_fitted = weighted_mean(fitted_deltap_wrt_model_energy, uncertainties)
            std_dev = float(pd.Series(deltap_wrt_6800).std(ddof=0))
            stderr = std_dev / (len(deltap_wrt_6800) ** 0.5) if deltap_wrt_6800 else 0.0

            results_file, fallback_warning = _write_results_file_with_fallback(
                ctrl,
                beam_energy=beam_energy,
                deltap_wrt_6800=deltap_wrt_6800,
                uncertainties=uncertainties,
                fitted_deltap_wrt_model_energy=fitted_deltap_wrt_model_energy,
                mean_wrt_6800=mean,
                mean_fitted_wrt_model_energy=mean_fitted,
                std_dev_wrt_6800=std_dev,
                stderr_wrt_6800=stderr,
            )

            worker_result.update(
                {
                    "result_payload": result_payload,
                    "beam_energy": beam_energy,
                    "deltap_wrt_6800": deltap_wrt_6800,
                    "fitted_deltap_wrt_model_energy": fitted_deltap_wrt_model_energy,
                    "mean": mean,
                    "mean_fitted": mean_fitted,
                    "std_dev": std_dev,
                    "results_file": results_file,
                    "magnet_knobs_path_for_info": magnet_knobs_path_for_info,
                    "corrector_knobs_path_for_info": corrector_knobs_path_for_info,
                    "fallback_warning": fallback_warning,
                }
            )
        except (SystemExit, KeyboardInterrupt):
            worker_error = InterruptedError("Interrupted by user.")
            return
        except Exception as exc:
            worker_error = exc

    worker = threading.Thread(target=run_worker, name="dpp-optimisation-worker", daemon=True)
    worker.start()
    ctrl._register_interrupt_thread(worker)
    hard_interrupted = False
    try:
        while worker.is_alive():
            ctrl._maybe_auto_escalate_interrupt()
            if ctrl._interrupt_hard_event.is_set():
                hard_interrupted = True
                break
            QApplication.processEvents()
            time.sleep(0.1)
        if not hard_interrupted:
            worker.join()
        elif worker_error is None:
            worker_error = InterruptedError("Interrupted by user.")

        if worker_error is not None:
            raise worker_error

        typed_worker_result = _payload_mapping(worker_result)
        result_payload = dict(_payload_mapping(typed_worker_result["result_payload"]))
        beam_energy = _require_float(typed_worker_result, "beam_energy")
        deltap_wrt_6800 = _payload_list_of_floats(
            typed_worker_result,
            keys=("deltap_wrt_6800",),
        )
        fitted_deltap_wrt_model_energy = _payload_list_of_floats(
            typed_worker_result,
            keys=("fitted_deltap_wrt_model_energy",),
        )
        mean = _optional_float(typed_worker_result, "mean")
        mean_fitted = _optional_float(typed_worker_result, "mean_fitted")
        std_dev = _require_float(typed_worker_result, "std_dev")
        results_file = _require_path(typed_worker_result, "results_file")
        magnet_knobs_path_for_info = _require_str(typed_worker_result, "magnet_knobs_path_for_info")
        corrector_knobs_path_for_info = _require_str(
            typed_worker_result,
            "corrector_knobs_path_for_info",
        )
        tab_results_file = _snapshot_results_for_tab(
            ctrl,
            results_file=results_file,
            origin_ctx=origin_ctx,
        )
        fallback_warning = _require_str(typed_worker_result, "fallback_warning")

        if fallback_warning:
            LOGGER.warning(fallback_warning)
            show_info_dialog(
                title="Results Save Warning",
                message=fallback_warning,
                parent=ctrl._view,
            )

        info_lines = [
            "Last run: SUCCESS",
            f"Execution: {result_payload.get('source', 'unknown')}",
            f"Arcs: {len(deltap_wrt_6800)}",
            f"Weighted mean delta-p (w.r.t. 6800 GeV): {_format_standard_number(mean)}",
            (
                "Weighted mean fitted delta-p "
                f"(w.r.t. model energy {beam_energy:.1f} GeV): "
                f"{_format_standard_number(mean_fitted)}"
            ),
            f"Std dev delta-p (w.r.t. 6800 GeV): {_format_standard_number(std_dev)}",
            f"Magnet knobs file: {magnet_knobs_path_for_info}",
            f"Corrector knobs file: {corrector_knobs_path_for_info}",
            f"Results file: {tab_results_file}",
        ]
        if fallback_warning:
            info_lines.append(fallback_warning)
        info_text = "\n".join(info_lines)

        if origin_ctx_exists():
            if is_origin_tab_active():
                ctrl._optimisation_results_file = tab_results_file
                ctrl._latest_deltap_wrt_6800_results = deltap_wrt_6800
                ctrl._latest_fitted_deltap_wrt_model_energy = fitted_deltap_wrt_model_energy
                ctrl._latest_model_energy_gev = beam_energy
                ctrl._view.update_optimisation_info(info_text)
            else:
                origin_ctx.optimisation_results_file = tab_results_file
                origin_ctx.latest_deltap_wrt_6800_results = list(deltap_wrt_6800)
                origin_ctx.latest_fitted_deltap_wrt_model_energy = list(
                    fitted_deltap_wrt_model_energy
                )
                origin_ctx.latest_model_energy_gev = beam_energy
                origin_ctx.optimisation_info_text = info_text
    except InterruptedError:
        LOGGER.warning("Optimisation interrupted by user.")
        interrupt_text = "Last run: INTERRUPTED\nOptimisation interrupted by user."
        if origin_ctx_exists():
            if is_origin_tab_active():
                ctrl._view.update_optimisation_info(interrupt_text)
            else:
                origin_ctx.optimisation_info_text = interrupt_text
    except Exception as e:
        LOGGER.exception("Error running optimisation: %s", e)
        failure_text = f"Last run: FAILED\n{e}"
        if origin_ctx_exists():
            if is_origin_tab_active():
                ctrl._view.update_optimisation_info(failure_text)
            else:
                origin_ctx.optimisation_info_text = failure_text
        show_error_dialog(
            title="Error Running Optimisation",
            message=f"Failed to run optimisation:\n{e}",
            parent=ctrl._view,
        )
    finally:
        ctrl._unregister_interrupt_thread(worker)
        ctrl._unregister_running_processes(1)
        ctrl._view.clear_bottom_progress()
        ctrl._optimisation_running = False
        ctrl._update_action_buttons()
