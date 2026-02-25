from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
from omc3.machine_data_extraction.mqt_extraction import get_mqt_vals
from omc3.machine_data_extraction.nxcals_knobs import get_energy
from pymadng_utils.io import save_knobs
from qtpy.QtWidgets import QApplication

from aba_optimiser.measurements import knob_extraction
from omc3_gui.dpp_optimisation.services import remote_jobs, ssh_service
from omc3_gui.ui_components.message_boxes import (
    show_error_dialog,
)

if TYPE_CHECKING:
    from omc3.machine_data_extraction.nxcals_knobs import NXCALSResult

    from omc3_gui.dpp_optimisation.main_controller import DppOptimisationController

LOGGER = logging.getLogger(__name__)
_KNOB_DOWNLOAD_LOCK = threading.Lock()


def _acquire_knob_download_slot(ctrl: DppOptimisationController | None = None):
    """Serialize knob downloads so SparkContext usage does not overlap."""
    if ctrl is None:
        _KNOB_DOWNLOAD_LOCK.acquire()
        return

    while not _KNOB_DOWNLOAD_LOCK.acquire(timeout=0.1):
        ctrl._maybe_auto_escalate_interrupt()
        ctrl._raise_if_interrupted()
        ctrl._view.update_bottom_progress(
            text=ctrl._format_running_processes_text(
                "Download Knobs: waiting for queued Spark slot..."
            ),
            value=0,
            maximum=1,
            indeterminate=True,
            visible=True,
        )
        QApplication.processEvents()


def build_dict_from_nxcal_result(result: list[NXCALSResult]) -> dict[str, float]:
    """Convert NXCALSResult to a dictionary of magnet strengths."""
    return {res.name: res.value for res in result}


def update_knob_files_summary(
    ctrl: DppOptimisationController,
    main_magnet_knobs: dict[str, float],
    corrector_knobs: dict[str, float],
    magnet_file: str | None = None,
    corrector_file: str | None = None,
):
    """Push knob file count and location details to the view."""
    ctrl._view.update_knob_files_summary(
        magnet_count=len(main_magnet_knobs),
        corrector_count=len(corrector_knobs),
        magnet_file=magnet_file or ctrl._get_magnet_knobs_display_path(),
        corrector_file=corrector_file or ctrl._get_corrector_knobs_display_path(),
    )


def compute_weighted_mean_and_variance(
    sub: pd.DataFrame,
    value_col: str,
    var_col: str,
) -> tuple[float, float]:
    """Compute inverse-variance weighted mean and variance of mean."""
    return remote_jobs.compute_weighted_mean_and_variance(sub, value_col, var_col)


def on_download_knobs(ctrl: DppOptimisationController):
    """Handle download knobs button click."""
    if not ctrl._validate_for_knob_download():
        return

    measurement_times = ctrl._extract_measurement_datetimes_from_files()
    if not measurement_times:
        show_error_dialog(
            title="Cannot Extract Times",
            message="Failed to extract measurement timestamps from filenames.\n\n"
            "Expected either YYYY_MM_DD_HH_MM_SS_mmm in the filename, or at least "
            "HH_MM_SS_mmm so file date can be used as fallback.",
            parent=ctrl._view,
        )
        return

    meas_time = min(measurement_times)
    _, beam, _, _ = ctrl._require_loaded_model_context()

    ctrl._register_running_processes(1)
    total_steps = 14
    remote_available, remote_host, remote_message = ctrl._is_remote_server_available_for_beam(beam)
    remote_work_dir = ctrl._get_remote_work_dir(beam)
    remote_warning = ""
    if not remote_available:
        remote_warning = (
            f"Remote artifact host unavailable ({remote_host}: {remote_message}). "
            "Saving knob files locally."
        )
        LOGGER.warning(remote_warning)

    ctrl._view.update_bottom_progress(
        text=ctrl._format_running_processes_text("Downloading knobs from LSA..."),
        value=0,
        maximum=total_steps,
        indeterminate=False,
        visible=True,
    )

    def set_step(step: int, text: str):
        ctrl._maybe_auto_escalate_interrupt()
        ctrl._raise_if_interrupted()
        ctrl._view.update_bottom_progress(
            text=ctrl._format_running_processes_text(f"Download Knobs: {text}"),
            value=step,
            maximum=total_steps,
            indeterminate=False,
            visible=True,
        )
        QApplication.processEvents()
        ctrl._maybe_auto_escalate_interrupt()
        ctrl._raise_if_interrupted()

    spark = None
    slot_acquired = False
    try:
        ctrl._raise_if_interrupted()
        set_step(1, "Waiting for queued Spark slot")
        _acquire_knob_download_slot(ctrl)
        slot_acquired = True

        set_step(2, "Importing NXCALS interfaces")
        from nxcals.spark_session_builder import get_or_create

        set_step(3, "Creating Spark session")
        spark = get_or_create()

        set_step(4, "Reading beam energy")
        energy, _ = get_energy(spark, meas_time)

        set_step(5, "Updating model beam energy from LSA")
        ctrl._apply_model_energy(float(energy))

        set_step(6, "Downloading MQ knobs")
        mq_results = knob_extraction.get_mq_vals(spark, meas_time, beam, energy=energy)
        set_step(7, "Downloading MQT knobs")
        mqt_results = get_mqt_vals(spark, meas_time, beam, energy=energy)
        set_step(8, "Downloading MS knobs")
        ms_results = knob_extraction.get_ms_vals(spark, meas_time, beam, energy=energy)
        set_step(9, "Downloading MB knobs")
        mb_results = knob_extraction.get_mb_vals(spark, meas_time, beam, energy=energy)
        set_step(10, "Downloading corrector knobs")
        corrector_results = knob_extraction.get_mcb_vals(spark, meas_time, beam, energy=energy)

        set_step(11, "Building knob dictionaries")
        mqt_knobs = build_dict_from_nxcal_result(mqt_results)
        ms_knobs = build_dict_from_nxcal_result(ms_results)
        mb_knobs = build_dict_from_nxcal_result(mb_results)
        mq_knobs = build_dict_from_nxcal_result(mq_results)
        corrector_knobs = build_dict_from_nxcal_result(corrector_results)

        main_magnet_knobs = {**mqt_knobs, **ms_knobs, **mb_knobs, **mq_knobs}
        set_step(12, "Saving knob files")
        if remote_available:
            try:
                work_dir, magnet_file, corrector_file = ctrl._save_knobs_via_ssh(
                    host=remote_host,
                    beam=beam,
                    main_magnet_knobs=main_magnet_knobs,
                    corrector_knobs=corrector_knobs,
                    remote_work_dir=remote_work_dir,
                )
                ctrl._remote_host = remote_host
                ctrl._remote_work_dir = work_dir
                ctrl._remote_magnet_knobs_file = magnet_file
                ctrl._remote_corrector_knobs_file = corrector_file
            except Exception as remote_exc:
                remote_warning = (
                    f"Remote knob save failed on {remote_host} ({remote_exc}). "
                    "Saving knob files locally."
                )
                LOGGER.warning(remote_warning)
                save_knobs(main_magnet_knobs, ctrl._get_magnet_knobs_file())
                save_knobs(corrector_knobs, ctrl._get_corrector_knobs_file())
                ctrl._clear_remote_artifacts()
        else:
            save_knobs(main_magnet_knobs, ctrl._get_magnet_knobs_file())
            save_knobs(corrector_knobs, ctrl._get_corrector_knobs_file())
            ctrl._clear_remote_artifacts()

        set_step(13, "Updating file inspection summary")
        update_knob_files_summary(ctrl, main_magnet_knobs, corrector_knobs)
        if remote_warning:
            ctrl._view.update_datafile_info(f"Last run: WARNING\n{remote_warning}")

        set_step(14, "Knob download complete")
        ctrl._knobs_downloaded = True
        ctrl._update_action_buttons()

    except InterruptedError:
        LOGGER.info("Knob download interrupted by user.")
        ctrl._view.update_datafile_info("Last run: INTERRUPTED\nKnob download interrupted by user.")
    except ImportError as e:
        show_error_dialog(
            title="Missing Dependency",
            message=(
                "NXCALS is required for knob download but is not installed or not available.\n\n"
                f"{e}"
            ),
            parent=ctrl._view,
        )
    except Exception as e:
        LOGGER.exception("Error downloading knobs: %s", e)
        show_error_dialog(
            title="Error Downloading Knobs",
            message=f"Failed to download knobs:\n{e}",
            parent=ctrl._view,
        )
    finally:
        ctrl._unregister_running_processes(1)
        if spark is not None:
            try:
                spark.stop()
            except Exception:
                LOGGER.warning("Failed to stop Spark session cleanly", exc_info=True)
        if slot_acquired:
            _KNOB_DOWNLOAD_LOCK.release()
        ctrl._view.clear_bottom_progress()


def on_create_datafile(ctrl: DppOptimisationController):
    """Handle create datafile button click."""
    if not ctrl._validate_for_datafile_creation():
        return

    _, beam, sequence_file, beam_energy = ctrl._require_loaded_model_context()
    measurement_files = ctrl._measurement_list_model.get_all_files()
    if ctrl._analysis_dir is None:
        show_error_dialog(
            title="No Analysis Selected",
            message="Please select an analysis directory first.",
            parent=ctrl._view,
        )
        return

    analysis_dir = ctrl._analysis_dir
    if not analysis_dir.exists():
        show_error_dialog(
            title="Analysis Directory Missing",
            message=f"Analysis directory does not exist:\n{analysis_dir}",
            parent=ctrl._view,
        )
        return
    local_output_path = ctrl._get_temp_work_dir() / ctrl.MEASUREMENT_DATAFILE_FILENAME
    ctrl._register_running_processes(1)

    ctrl._view.update_bottom_progress(
        text=ctrl._format_running_processes_text("Creating datafile..."),
        value=0,
        maximum=6,
        indeterminate=False,
        visible=True,
    )

    def set_step(step: int, text: str):
        ctrl._maybe_auto_escalate_interrupt()
        ctrl._raise_if_interrupted()
        ctrl._view.update_bottom_progress(
            text=ctrl._format_running_processes_text(f"Create Datafile: {text}"),
            value=step,
            maximum=6,
            indeterminate=False,
            visible=True,
        )
        QApplication.processEvents()
        ctrl._maybe_auto_escalate_interrupt()
        ctrl._raise_if_interrupted()

    try:
        ctrl._raise_if_interrupted()
        set_step(1, "Checking beam server availability")
        available, host, message = ctrl._is_remote_server_available_for_beam(beam)

        remote_warning = ""
        result_data: dict[str, object]
        if available:
            remote_output_path = Path(ctrl._get_remote_work_dir(beam)) / ctrl.MEASUREMENT_DATAFILE_FILENAME
            remote_work_dir = str(remote_output_path.parent)
            set_step(2, f"Running create-datafile on {host}")
            try:
                result_data = create_datafile_via_ssh(
                    ctrl,
                    host=host,
                    beam=beam,
                    sequence_file=sequence_file,
                    beam_energy=beam_energy,
                    measurement_files=measurement_files,
                    analysis_dir=analysis_dir,
                    bad_bpms=ctrl._bad_bpms,
                    output_path=remote_output_path,
                    remote_work_dir=remote_work_dir,
                )
            except Exception as remote_exc:
                remote_warning = (
                    f"WARNING: Remote execution on {host} failed ({remote_exc}). "
                    "Falling back to local execution."
                )
                LOGGER.warning(remote_warning)
                set_step(2, "Remote failed, processing locally")
                result_data = create_datafile_locally(
                    ctrl,
                    beam=beam,
                    measurement_files=measurement_files,
                    analysis_dir=analysis_dir,
                    bad_bpms=ctrl._bad_bpms,
                    output_path=local_output_path,
                    set_step=set_step,
                )
        else:
            remote_warning = (
                f"WARNING: Remote server {host} unavailable ({message}). "
                "Falling back to local execution."
            )
            LOGGER.warning(remote_warning)
            set_step(2, "Remote unavailable, processing locally")
            result_data = create_datafile_locally(
                ctrl,
                beam=beam,
                measurement_files=measurement_files,
                analysis_dir=analysis_dir,
                bad_bpms=ctrl._bad_bpms,
                output_path=local_output_path,
                set_step=set_step,
            )

        set_step(5, "Updating state")
        source_label = str(result_data.get("source", "local"))
        output_path_str = str(result_data["output_path"])
        display_output_path = output_path_str
        if source_label.startswith("remote:"):
            ctrl._remote_host = host
            ctrl._remote_work_dir = str(Path(output_path_str).parent)
            ctrl._remote_measurement_datafile = output_path_str
            ctrl._measurement_datafile = None
            display_output_path = ctrl._format_remote_path_for_display(output_path_str)
        else:
            ctrl._measurement_datafile = Path(output_path_str)
            ctrl._remote_measurement_datafile = None
        ctrl._bad_bpms = list(result_data["bad_bpms"])
        ctrl._datafile_created = True
        ctrl._update_action_buttons()

        set_step(6, "Done")
        LOGGER.info(
            "Created measurement datafile at %s with %d rows and %d bad BPMs",
            output_path_str,
            int(result_data["rows"]),
            len(ctrl._bad_bpms),
        )
        info_lines = [
            "Last run: SUCCESS",
            f"Execution: {source_label}",
            f"File: {display_output_path}",
            f"Rows: {int(result_data['rows'])}",
            f"Bad BPMs: {len(ctrl._bad_bpms)}",
        ]
        if remote_warning:
            info_lines.append(remote_warning)
        ctrl._view.update_datafile_info("\n".join(info_lines))
        ctrl._view.update_optimisation_info("Datafile ready. You can now run optimisation.")

    except InterruptedError:
        LOGGER.info("Create datafile interrupted by user.")
        ctrl._view.update_datafile_info("Last run: INTERRUPTED\nDatafile creation interrupted by user.")
    except ImportError as e:
        ctrl._view.update_datafile_info(f"Last run: FAILED\n{e}")
        show_error_dialog(
            title="Missing Dependency",
            message=(
                "Measurement processing requires aba_optimiser dependencies that are not "
                f"available.\n\n{e}"
            ),
            parent=ctrl._view,
        )
    except Exception as e:
        LOGGER.exception("Error creating datafile: %s", e)
        ctrl._view.update_datafile_info(f"Last run: FAILED\n{e}")
        show_error_dialog(
            title="Error Creating Datafile",
            message=f"Failed to create datafile:\n{e}",
            parent=ctrl._view,
        )
    finally:
        ctrl._unregister_running_processes(1)
        ctrl._view.clear_bottom_progress()


def create_datafile_locally(
    ctrl: DppOptimisationController,
    beam: int,
    measurement_files: list[Path],
    analysis_dir: Path,
    bad_bpms: list[str],
    output_path: Path,
    set_step,
) -> dict[str, object]:
    """Create the datafile locally and return summary fields."""
    set_step(3, "Importing processing interface")
    set_step(4, "Processing and averaging measurements")
    _, _, sequence_file, beam_energy = ctrl._require_loaded_model_context()
    payload = {
        "beam": beam,
        "sequence_file": str(sequence_file),
        "beam_energy": float(beam_energy),
        "measurement_files": [str(path) for path in measurement_files],
        "analysis_dir": str(analysis_dir),
        "bad_bpms": list(bad_bpms),
        "output_path": str(output_path),
        "source": "local",
    }
    return remote_jobs.create_datafile_job(payload)


def create_datafile_via_ssh(
    ctrl: DppOptimisationController,
    host: str,
    beam: int,
    sequence_file: Path,
    beam_energy: float,
    measurement_files: list[Path],
    analysis_dir: Path,
    bad_bpms: list[str],
    output_path: Path,
    remote_work_dir: str | None = None,
) -> dict[str, object]:
    """Create the datafile on a remote host through SSH."""
    remote_sequence_file = ctrl._resolve_sequence_file_for_ssh(
        host,
        beam,
        sequence_file,
        remote_work_dir=remote_work_dir,
    )
    payload = {
        "beam": beam,
        "sequence_file": remote_sequence_file,
        "beam_energy": float(beam_energy),
        "measurement_files": [str(path) for path in measurement_files],
        "analysis_dir": str(analysis_dir),
        "bad_bpms": list(bad_bpms),
        "output_path": str(output_path),
        "source": f"remote:{beam}@{host}",
    }
    return ssh_service.run_remote_json_job(
        ctrl,
        host=host,
        module="omc3_gui.dpp_optimisation.services.remote_jobs",
        function="create_datafile_job",
        payload=payload,
        marker="OMC3_GUI_RESULT=",
    )


def download_knobs_locally_worker(
    ctrl: DppOptimisationController,
    beam: int,
    meas_time: pd.Timestamp,
    magnet_file: Path,
    corrector_file: Path,
) -> dict[str, object]:
    """Download knobs locally and save files in temp work dir."""
    from nxcals.spark_session_builder import get_or_create

    spark = None
    slot_acquired = False
    try:
        _acquire_knob_download_slot()
        slot_acquired = True
        spark = get_or_create()
        energy, _ = get_energy(spark, meas_time)
        mq_results = knob_extraction.get_mq_vals(spark, meas_time, beam, energy=energy)
        mqt_results = get_mqt_vals(spark, meas_time, beam, energy=energy)
        ms_results = knob_extraction.get_ms_vals(spark, meas_time, beam, energy=energy)
        mb_results = knob_extraction.get_mb_vals(spark, meas_time, beam, energy=energy)
        corrector_results = knob_extraction.get_mcb_vals(spark, meas_time, beam, energy=energy)

        mqt_knobs = build_dict_from_nxcal_result(mqt_results)
        ms_knobs = build_dict_from_nxcal_result(ms_results)
        mb_knobs = build_dict_from_nxcal_result(mb_results)
        mq_knobs = build_dict_from_nxcal_result(mq_results)
        corrector_knobs = build_dict_from_nxcal_result(corrector_results)
        main_magnet_knobs = {**mqt_knobs, **ms_knobs, **mb_knobs, **mq_knobs}

        save_knobs(main_magnet_knobs, magnet_file)
        save_knobs(corrector_knobs, corrector_file)

        return {
            "energy": float(energy),
            "main_magnet_knobs": main_magnet_knobs,
            "corrector_knobs": corrector_knobs,
            "magnet_file": str(magnet_file),
            "corrector_file": str(corrector_file),
            "source": "local",
        }
    finally:
        if spark is not None:
            try:
                spark.stop()
            except Exception:
                LOGGER.warning("Failed to stop Spark session cleanly", exc_info=True)
        if slot_acquired:
            _KNOB_DOWNLOAD_LOCK.release()


def create_datafile_worker(
    ctrl: DppOptimisationController,
    beam: int,
    sequence_file: Path,
    beam_energy: float,
    measurement_files: list[Path],
    analysis_dir: Path,
    bad_bpms: list[str],
    output_path: Path,
    remote_work_dir: str | None = None,
) -> dict[str, object]:
    """Create datafile, preferring SSH and falling back to local."""
    available, host, message = ctrl._is_remote_server_available_for_beam(beam)
    if available:
        try:
            result_data = create_datafile_via_ssh(
                ctrl,
                host=host,
                beam=beam,
                sequence_file=sequence_file,
                beam_energy=beam_energy,
                measurement_files=measurement_files,
                analysis_dir=analysis_dir,
                bad_bpms=bad_bpms,
                output_path=output_path,
                remote_work_dir=remote_work_dir,
            )
            result_data["remote_host"] = host
            return result_data
        except Exception as remote_exc:
            LOGGER.warning(
                "Remote create-datafile failed on %s (%s). Falling back to local execution.",
                host,
                remote_exc,
            )
            local = create_datafile_locally(
                ctrl,
                beam=beam,
                measurement_files=measurement_files,
                analysis_dir=analysis_dir,
                bad_bpms=bad_bpms,
                output_path=output_path,
                set_step=lambda *_args, **_kwargs: None,
            )
            local["warning"] = (
                f"WARNING: Remote execution on {host} failed ({remote_exc}). "
                "Falling back to local execution."
            )
            return local

    LOGGER.warning("Remote server %s unavailable (%s). Creating datafile locally.", host, message)
    local = create_datafile_locally(
        ctrl,
        beam=beam,
        measurement_files=measurement_files,
        analysis_dir=analysis_dir,
        bad_bpms=bad_bpms,
        output_path=output_path,
        set_step=lambda *_args, **_kwargs: None,
    )
    local["warning"] = (
        f"WARNING: Remote server {host} unavailable ({message}). Falling back to local execution."
    )
    return local


def on_prepare_inputs_parallel(ctrl: DppOptimisationController):
    """Run knob download and datafile creation in parallel."""
    if not ctrl._validate_for_knob_download():
        return
    _, beam, sequence_file, beam_energy = ctrl._require_loaded_model_context()
    if ctrl._analysis_dir is None:
        show_error_dialog(
            title="No Analysis Selected",
            message="Please select an analysis directory first.",
            parent=ctrl._view,
        )
        return
    measurement_files = ctrl._measurement_list_model.get_all_files()
    measurement_times = ctrl._extract_measurement_datetimes_from_files()
    if not measurement_times:
        show_error_dialog(
            title="Cannot Extract Times",
            message=(
                "Failed to extract measurement timestamps from filenames.\n\n"
                "Expected either YYYY_MM_DD_HH_MM_SS_mmm in the filename, or at least "
                "HH_MM_SS_mmm so file date can be used as fallback."
            ),
            parent=ctrl._view,
        )
        return

    origin_ctx = ctrl._optimisation_tabs[ctrl._active_tab_index]
    if origin_ctx.prepare_inputs_running:
        show_error_dialog(
            title="Preparation Already Running",
            message="Prepare Inputs is already running for this tab.",
            parent=ctrl._view,
        )
        return
    origin_ctx.prepare_inputs_running = True
    if 0 <= ctrl._active_tab_index < len(ctrl._optimisation_tabs):
        ctrl._prepare_inputs_running = True
        ctrl._update_action_buttons()

    analysis_dir = ctrl._analysis_dir
    work_dir = ctrl._get_temp_work_dir()
    remote_work_dir = ctrl._get_remote_work_dir(beam)
    output_path = work_dir / ctrl.MEASUREMENT_DATAFILE_FILENAME
    magnet_file = work_dir / ctrl.MAGNET_KNOBS_FILENAME
    corrector_file = work_dir / ctrl.CORRECTOR_KNOBS_FILENAME
    meas_time = min(measurement_times)
    worker_results: dict[str, dict[str, object]] = {}
    worker_errors: dict[str, Exception] = {}
    bad_bpms_snapshot = list(ctrl._bad_bpms)

    def is_origin_tab_active() -> bool:
        return (
            0 <= ctrl._active_tab_index < len(ctrl._optimisation_tabs)
            and ctrl._optimisation_tabs[ctrl._active_tab_index] is origin_ctx
        )

    def format_knob_summary_text(
        magnet_count: int,
        corrector_count: int,
        magnet_file_text: str,
        corrector_file_text: str,
    ) -> str:
        return (
            f"Main magnet knobs: {magnet_count}\n"
            f"Corrector knobs: {corrector_count}\n"
            f"Magnet file: {magnet_file_text}\n"
            f"Corrector file: {corrector_file_text}"
        )

    def origin_ctx_exists() -> bool:
        return any(ctx is origin_ctx for ctx in ctrl._optimisation_tabs)

    def apply_knobs_result():
        knobs_data = worker_results["knobs"]
        magnet_path_str = str(knobs_data["magnet_file"])
        corrector_path_str = str(knobs_data["corrector_file"])
        if is_origin_tab_active():
            ctrl._apply_model_energy(float(knobs_data["energy"]))
            ctrl._remote_magnet_knobs_file = None
            ctrl._remote_corrector_knobs_file = None
            ctrl._knobs_downloaded = True
            update_knob_files_summary(
                ctrl,
                main_magnet_knobs=knobs_data["main_magnet_knobs"],
                corrector_knobs=knobs_data["corrector_knobs"],
                magnet_file=magnet_path_str,
                corrector_file=corrector_path_str,
            )
        else:
            if origin_ctx.model_info is not None:
                origin_ctx.model_info.beam_energy = float(knobs_data["energy"])
            origin_ctx.remote_magnet_knobs_file = None
            origin_ctx.remote_corrector_knobs_file = None
            origin_ctx.knobs_downloaded = True
            origin_ctx.knob_files_summary_text = format_knob_summary_text(
                magnet_count=len(knobs_data["main_magnet_knobs"]),
                corrector_count=len(knobs_data["corrector_knobs"]),
                magnet_file_text=magnet_path_str,
                corrector_file_text=corrector_path_str,
            )

    def apply_datafile_result():
        datafile_data = worker_results["datafile"]
        source_label = str(datafile_data.get("source", "local"))
        output_path_str = str(datafile_data["output_path"])
        display_output_path = output_path_str
        bad_bpms_result = list(datafile_data["bad_bpms"])
        remote_host = str(datafile_data.get("remote_host", ""))
        if is_origin_tab_active():
            if source_label.startswith("remote:"):
                remote_host_active = str(datafile_data.get("remote_host", ctrl._remote_host or ""))
                if remote_host_active:
                    ctrl._remote_host = remote_host_active
                ctrl._remote_work_dir = str(Path(output_path_str).parent)
                ctrl._remote_measurement_datafile = output_path_str
                ctrl._measurement_datafile = None
                display_output_path = ctrl._format_remote_path_for_display(output_path_str)
            else:
                ctrl._measurement_datafile = Path(output_path_str)
                ctrl._remote_measurement_datafile = None
            ctrl._bad_bpms = bad_bpms_result
            ctrl._datafile_created = True
        else:
            if source_label.startswith("remote:"):
                host_for_display = remote_host or "remote"
                display_output_path = f"{output_path_str} [remote:{host_for_display}]"
                origin_ctx.remote_host = remote_host or origin_ctx.remote_host
                origin_ctx.remote_work_dir = str(Path(output_path_str).parent)
                origin_ctx.remote_measurement_datafile = output_path_str
                origin_ctx.measurement_datafile = None
            else:
                origin_ctx.measurement_datafile = Path(output_path_str)
                origin_ctx.remote_measurement_datafile = None
            origin_ctx.bad_bpms = bad_bpms_result
            origin_ctx.datafile_created = True

        info_lines = [
            "Last run: SUCCESS",
            f"Execution: {source_label}",
            f"File: {display_output_path}",
            f"Rows: {int(datafile_data['rows'])}",
            f"Bad BPMs: {len(bad_bpms_result)}",
        ]
        warning = str(datafile_data.get("warning", ""))
        if warning:
            info_lines.append(warning)
        if is_origin_tab_active():
            ctrl._view.update_datafile_info("\n".join(info_lines))
        else:
            origin_ctx.datafile_info_text = "\n".join(info_lines)

    applied_knobs = False
    applied_datafile = False

    ctrl._register_running_processes(2)
    ctrl._register_parallel_inputs(2)
    global_finished, total_parallel_inputs = ctrl._get_parallel_inputs_progress()
    total_parallel_inputs = max(total_parallel_inputs, 2)
    ctrl._view.update_bottom_progress(
        text=f"Preparing inputs in parallel... ({global_finished}/{total_parallel_inputs} finished)",
        value=global_finished,
        maximum=total_parallel_inputs,
        indeterminate=False,
        visible=True,
    )

    def run_knobs():
        try:
            worker_results["knobs"] = download_knobs_locally_worker(
                ctrl,
                beam=beam,
                meas_time=meas_time,
                magnet_file=magnet_file,
                corrector_file=corrector_file,
            )
        except BaseException as exc:
            if isinstance(exc, (SystemExit, KeyboardInterrupt, InterruptedError)):
                worker_errors["knobs"] = InterruptedError("Interrupted by user.")
            else:
                worker_errors["knobs"] = exc if isinstance(exc, Exception) else Exception(str(exc))

    def run_datafile():
        try:
            worker_results["datafile"] = create_datafile_worker(
                ctrl,
                beam=beam,
                sequence_file=sequence_file,
                beam_energy=beam_energy,
                measurement_files=measurement_files,
                analysis_dir=analysis_dir,
                bad_bpms=bad_bpms_snapshot,
                output_path=output_path,
                remote_work_dir=remote_work_dir,
            )
        except BaseException as exc:
            if isinstance(exc, (SystemExit, KeyboardInterrupt, InterruptedError)):
                worker_errors["datafile"] = InterruptedError("Interrupted by user.")
            else:
                worker_errors["datafile"] = exc if isinstance(exc, Exception) else Exception(str(exc))

    knobs_thread = threading.Thread(target=run_knobs, name="dpp-knobs-worker", daemon=True)
    datafile_thread = threading.Thread(
        target=run_datafile,
        name="dpp-datafile-worker",
        daemon=True,
    )
    knobs_thread.start()
    datafile_thread.start()
    ctrl._register_interrupt_thread(knobs_thread)
    ctrl._register_interrupt_thread(datafile_thread)

    reported_finished = 0
    hard_interrupted = False
    try:
        while knobs_thread.is_alive() or datafile_thread.is_alive():
            ctrl._maybe_auto_escalate_interrupt()
            if ctrl._interrupt_hard_event.is_set():
                hard_interrupted = True
                break
            finished = int(not knobs_thread.is_alive()) + int(not datafile_thread.is_alive())
            if finished > reported_finished:
                ctrl._mark_parallel_inputs_completed(finished - reported_finished)
                reported_finished = finished
            global_finished, total_parallel_inputs = ctrl._get_parallel_inputs_progress()
            total_parallel_inputs = max(total_parallel_inputs, 2)
            ctrl._view.update_bottom_progress(
                text=f"Preparing inputs in parallel... ({global_finished}/{total_parallel_inputs} finished)",
                value=global_finished,
                maximum=total_parallel_inputs,
                indeterminate=False,
                visible=True,
            )
            if (
                origin_ctx_exists()
                and not ctrl._interrupt_requested()
                and not applied_knobs
                and "knobs" in worker_results
            ):
                apply_knobs_result()
                applied_knobs = True
                if is_origin_tab_active():
                    ctrl._update_action_buttons()
            if (
                origin_ctx_exists()
                and not ctrl._interrupt_requested()
                and not applied_datafile
                and "datafile" in worker_results
            ):
                apply_datafile_result()
                applied_datafile = True
                if is_origin_tab_active():
                    ctrl._update_action_buttons()
            QApplication.processEvents()
            time.sleep(0.1)
        if not hard_interrupted:
            knobs_thread.join()
            datafile_thread.join()
            finished = 2
            if finished > reported_finished:
                ctrl._mark_parallel_inputs_completed(finished - reported_finished)
                reported_finished = finished
    finally:
        ctrl._unregister_interrupt_thread(knobs_thread)
        ctrl._unregister_interrupt_thread(datafile_thread)
        global_finished, total_parallel_inputs = ctrl._get_parallel_inputs_progress()
        total_parallel_inputs = max(total_parallel_inputs, 2)
        ctrl._view.update_bottom_progress(
            text=f"Preparing inputs in parallel... ({global_finished}/{total_parallel_inputs} finished)",
            value=global_finished,
            maximum=total_parallel_inputs,
            indeterminate=False,
            visible=True,
        )
        ctrl._unregister_running_processes(2)
        origin_ctx.prepare_inputs_running = False
        if 0 <= ctrl._active_tab_index < len(ctrl._optimisation_tabs):
            ctrl._prepare_inputs_running = ctrl._optimisation_tabs[
                ctrl._active_tab_index
            ].prepare_inputs_running
        else:
            ctrl._prepare_inputs_running = False
        ctrl._update_action_buttons()

    if not any(ctx is origin_ctx for ctx in ctrl._optimisation_tabs):
        ctrl._view.clear_bottom_progress()
        return

    if not ctrl._interrupt_requested() and not applied_knobs and "knobs" in worker_results:
        apply_knobs_result()
        applied_knobs = True

    if not ctrl._interrupt_requested() and not applied_datafile and "datafile" in worker_results:
        apply_datafile_result()
        applied_datafile = True

    ctrl._update_action_buttons()
    ctrl._view.clear_bottom_progress()

    if ctrl._interrupt_requested():
        if is_origin_tab_active():
            ctrl._view.update_optimisation_info("Prepare inputs interrupted by user.")
        else:
            origin_ctx.optimisation_info_text = "Prepare inputs interrupted by user."
        return

    if worker_errors:
        lines = ["One or more preparation tasks failed:"]
        for name, exc in worker_errors.items():
            lines.append(f"- {name}: {exc}")
        optimisation_text = "Last run: PARTIAL FAILURE\n" + "\n".join(lines)
        if is_origin_tab_active():
            ctrl._view.update_optimisation_info(optimisation_text)
        else:
            origin_ctx.optimisation_info_text = optimisation_text
        show_error_dialog(
            title="Parallel Preparation Failed",
            message="\n".join(lines),
            parent=ctrl._view,
        )
        return

    success_text = "Preparation complete: knobs downloaded and datafile created."
    if is_origin_tab_active():
        ctrl._view.update_optimisation_info(success_text)
    else:
        origin_ctx.optimisation_info_text = success_text
