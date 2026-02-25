from __future__ import annotations

import json
import shlex
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omc3_gui.dpp_optimisation.main_controller import DppOptimisationController


def run_remote_json_job(
    ctrl: DppOptimisationController,
    *,
    host: str,
    module: str,
    function: str,
    payload: dict[str, object],
    marker: str,
) -> dict[str, object]:
    """Execute a Python function remotely over SSH and parse JSON result.

    The remote function must have signature `fn(payload: dict) -> dict`.
    """
    payload_json = json.dumps(payload)
    # Keep one small, generic bootstrap string for all remote jobs.
    script = (
        "import importlib\n"
        "import json\n"
        f"payload = json.loads({payload_json!r})\n"
        f"mod = importlib.import_module({module!r})\n"
        f"fn = getattr(mod, {function!r})\n"
        "result = fn(payload)\n"
        f"print({marker!r} + json.dumps(result))\n"
    )

    remote_python = ctrl._get_remote_python_executable(host)
    result = ctrl._run_ssh_with_stdin(
        host=host,
        remote_command=f"{shlex.quote(remote_python)} -",
        stdin_text=script,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "Unknown remote execution error"
        raise RuntimeError(f"Remote job failed on {host}: {stderr}")

    payload_line = ""
    for line in reversed(result.stdout.splitlines()):
        if line.startswith(marker):
            payload_line = line[len(marker) :]
            break
    if not payload_line:
        raise RuntimeError(f"Remote job on {host} did not return result payload.")

    parsed = json.loads(payload_line)
    if not isinstance(parsed, dict):
        raise RuntimeError("Invalid remote result payload type.")
    return parsed
