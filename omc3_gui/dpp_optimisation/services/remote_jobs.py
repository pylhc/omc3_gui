from __future__ import annotations

import inspect
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
from aba_optimiser.accelerators import LHC
from aba_optimiser.config import OptimiserConfig as AbaOptimiserConfig
from aba_optimiser.config import SimulationConfig as AbaSimulationConfig
from aba_optimiser.mad import GenericMadInterface
from aba_optimiser.measurements.create_datafile import (
    convert_measurements,
    detect_bad_bpms,
    load_files,
    process_single_dataframe,
)
from aba_optimiser.measurements.optimise_closed_orbit import optimise_ranges

from omc3_gui.dpp_optimisation.defaults import build_optimisation_range_config


def compute_weighted_mean_and_variance(
    sub: pd.DataFrame,
    value_col: str,
    var_col: str,
) -> tuple[float, float]:
    values = pd.to_numeric(sub[value_col], errors="coerce")
    variances = pd.to_numeric(sub[var_col], errors="coerce")
    valid = values.notna() & variances.notna() & (variances > 0.0)

    if valid.any():
        weights = 1.0 / variances[valid]
        sum_weights = float(weights.sum())
        if sum_weights > 0.0:
            mu = float((values[valid] * weights).sum() / sum_weights)
            return mu, float(1.0 / sum_weights)

    finite_values = values.dropna()
    if finite_values.empty:
        return float("nan"), float("nan")
    mu = float(finite_values.mean())
    n = int(finite_values.count())
    if n >= 2:
        var_mean = float(finite_values.var(ddof=1) / n)
    else:
        var_mean = float("nan")
    return mu, var_mean


def build_config_kwargs(
    cls,
    values: dict[str, object],
    fallbacks: dict[str, object],
) -> dict[str, object]:
    sig = inspect.signature(cls)
    kwargs: dict[str, object] = {}
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        if param.kind not in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            continue
        if name in values:
            kwargs[name] = values[name]
        elif name in fallbacks:
            kwargs[name] = fallbacks[name]
    return kwargs


def _max_measurement_workers(num_measurements: int) -> int:
    """Return worker count capped to one quarter of available CPU cores."""
    cpu_count = os.cpu_count() or 1
    quarter_cpus = max(1, cpu_count // 4)
    return max(1, min(num_measurements, quarter_cpus))


def create_datafile_job(payload: dict[str, object]) -> dict[str, object]:
    """Create weighted-averaged datafile from payload config."""
    beam = int(payload["beam"])
    sequence_file = Path(str(payload["sequence_file"]))
    beam_energy = float(payload["beam_energy"])
    measurement_files = [Path(str(p)) for p in payload["measurement_files"]]
    analysis_dir = Path(str(payload["analysis_dir"]))
    bad_bpms = list(payload.get("bad_bpms", []))
    output_path = Path(str(payload["output_path"]))
    source = str(payload.get("source", "local"))

    measurements = load_files(measurement_files)
    combined = convert_measurements(measurements, bad_bpms, combine_measurements=True)

    accelerator = LHC(
        beam=beam,
        sequence_file=sequence_file,
        beam_energy=beam_energy,
        optimise_energy=True,
    )
    mad_interface = GenericMadInterface(accelerator=accelerator, bpm_pattern="^BPM")
    tws = mad_interface.run_twiss()

    max_workers = _max_measurement_workers(len(combined))
    args = [(i, df) for i, df in enumerate(combined)]

    def _process_one(df_with_index: tuple[int, pd.DataFrame]) -> pd.DataFrame:
        _, processed_df = process_single_dataframe(
            df_with_index=df_with_index,
            tws=tws,
            bad_bpms=bad_bpms,
            analysis_dir=analysis_dir,
            use_uniform_vars=False,
            beam=beam,
        )
        return processed_df

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        processed = list(executor.map(_process_one, args))

    if not processed:
        raise RuntimeError("No dataframes were processed.")

    pzs = pd.concat(processed, ignore_index=True)
    pzs["name"] = pzs["name"].astype("category")
    pzs["turn"] = pzs["turn"].astype("int32")
    pzs.attrs["DPP_EST"] = sum(df.attrs["DPP_EST"] for df in processed) / len(processed)

    all_bpms = set(mad_interface.all_bpms)
    detect_bad_bpms(pzs, all_bpms, bad_bpms)

    required_columns = ["x", "y", "px", "py", "var_x", "var_y", "var_px", "var_py"]
    missing_columns = [col for col in required_columns if col not in pzs.columns]
    if missing_columns:
        raise ValueError(
            f"Missing expected measurement columns for weighted averaging: {missing_columns}"
        )

    averaged_rows: list[dict[str, object]] = []
    for name, sub in pzs.groupby("name", observed=False):
        mu_x, vm_x = compute_weighted_mean_and_variance(sub, "x", "var_x")
        mu_y, vm_y = compute_weighted_mean_and_variance(sub, "y", "var_y")
        mu_px, vm_px = compute_weighted_mean_and_variance(sub, "px", "var_px")
        mu_py, vm_py = compute_weighted_mean_and_variance(sub, "py", "var_py")
        averaged_rows.append(
            {
                "name": name,
                "x": mu_x,
                "y": mu_y,
                "px": mu_px,
                "py": mu_py,
                "var_x": vm_x,
                "var_y": vm_y,
                "var_px": vm_px,
                "var_py": vm_py,
            }
        )

    averaged = pd.DataFrame(averaged_rows)
    new_rows: list[dict[str, object]] = []
    for turn in (1, 2, 3):
        for row in averaged.itertuples(index=False):
            new_row = {"name": row.name, "turn": turn, "kick_plane": "xy"}
            for col in required_columns:
                new_row[col] = getattr(row, col)
            new_rows.append(new_row)
    processed_df = pd.DataFrame(new_rows)
    processed_df["name"] = processed_df["name"].astype("category")
    processed_df["turn"] = processed_df["turn"].astype("int32")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    processed_df.to_parquet(output_path)

    bad_bpms_sorted = sorted(set(bad_bpms))
    with (output_path.parent / "bad_bpms.txt").open("w") as f:
        for bpm in bad_bpms_sorted:
            f.write(f"{bpm}\n")

    return {
        "rows": len(processed_df),
        "bad_bpms": bad_bpms_sorted,
        "output_path": str(output_path),
        "source": source,
    }


def run_optimisation_job(payload: dict[str, object]) -> dict[str, object]:
    """Run arc optimisation from payload config."""
    beam = int(payload["beam"])
    energy = float(payload["energy"])
    sequence_file = Path(str(payload["sequence_file"]))
    magnet_knobs_file = Path(str(payload["magnet_knobs_file"]))
    corrector_knobs_file = Path(str(payload["corrector_knobs_file"]))
    measurement_file = Path(str(payload["measurement_file"]))
    bad_bpms = list(payload.get("bad_bpms", []))
    arcs = list(payload.get("arcs", []))
    source = str(payload.get("source", "local"))

    range_config = build_optimisation_range_config(arcs=arcs, beam=beam)

    optimiser_config = AbaOptimiserConfig(
        **build_config_kwargs(
            AbaOptimiserConfig,
            dict(payload.get("optimiser_config", {})),
            {"expected_rel_error": 0.0},
        )
    )
    simulation_config = AbaSimulationConfig(
        **build_config_kwargs(
            AbaSimulationConfig,
            dict(payload.get("simulation_config", {})),
            {"optimise_momenta": True, "optimise_correctors": False},
        )
    )

    results, uncertainties, fitted_deltaps, e_ref = optimise_ranges(
        range_config=range_config,
        range_type="arc",
        beam=beam,
        optimiser_config=optimiser_config,
        simulation_config=simulation_config,
        sequence_path=sequence_file,
        corrector_knobs_file=corrector_knobs_file,
        tune_knobs_file=magnet_knobs_file,
        measurement_file=measurement_file,
        bad_bpms=bad_bpms,
        title="gui",
        energy=energy,
        write_tensorboard_logs=False,
    )

    return {
        "source": source,
        "deltap": [float(v) for v in results],
        "uncertainties": [float(v) for v in uncertainties],
        "fitted_deltaps": [float(v) for v in fitted_deltaps],
        "e_ref": e_ref,
    }
