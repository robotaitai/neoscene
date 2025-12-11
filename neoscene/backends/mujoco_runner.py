"""MuJoCo simulation runner.

This module provides functionality to run MuJoCo simulations from MJCF XML.
"""

import tempfile
import time
from pathlib import Path
from typing import Optional

import mujoco
import mujoco.viewer


def run_mjcf_xml(
    xml: str,
    realtime: bool = True,
    max_duration: Optional[float] = None,
) -> None:
    """Run a MuJoCo simulation from an MJCF XML string.

    Opens the MuJoCo viewer and runs the simulation interactively.

    Args:
        xml: MJCF XML string to simulate.
        realtime: If True, sync simulation to real time.
        max_duration: Optional maximum simulation duration in seconds.
    """
    # Write XML to a temporary file (MuJoCo needs file paths for includes)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".xml", delete=False
    ) as f:
        f.write(xml)
        temp_path = Path(f.name)

    try:
        # Load model and create data
        model = mujoco.MjModel.from_xml_path(str(temp_path))
        data = mujoco.MjData(model)

        # Launch viewer
        with mujoco.viewer.launch_passive(model, data) as viewer:
            start_time = time.time()

            while viewer.is_running():
                step_start = time.time()

                # Step simulation
                mujoco.mj_step(model, data)

                # Sync viewer
                viewer.sync()

                # Real-time sync
                if realtime:
                    elapsed = time.time() - step_start
                    sleep_time = model.opt.timestep - elapsed
                    if sleep_time > 0:
                        time.sleep(sleep_time)

                # Check duration limit
                if max_duration is not None:
                    if time.time() - start_time > max_duration:
                        break

    finally:
        # Clean up temp file
        temp_path.unlink(missing_ok=True)


def run_mjcf_file(path: Path, **kwargs) -> None:
    """Run a MuJoCo simulation from an MJCF XML file.

    Args:
        path: Path to the MJCF XML file.
        **kwargs: Additional arguments passed to run_mjcf_xml.
    """
    xml = path.read_text()
    run_mjcf_xml(xml, **kwargs)


def validate_mjcf_xml(xml: str) -> bool:
    """Validate that an MJCF XML string can be loaded by MuJoCo.

    Args:
        xml: MJCF XML string to validate.

    Returns:
        True if the XML is valid and can be loaded.

    Raises:
        Exception: If the XML cannot be parsed by MuJoCo.
    """
    # Write to temp file for includes to work
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".xml", delete=False
    ) as f:
        f.write(xml)
        temp_path = Path(f.name)

    try:
        model = mujoco.MjModel.from_xml_path(str(temp_path))
        _ = mujoco.MjData(model)
        return True
    finally:
        temp_path.unlink(missing_ok=True)

