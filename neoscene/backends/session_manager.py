"""Scene Session Manager - tracks scene sessions and manages MuJoCo viewers.

MVP behavior: on each update, restart the viewer with the new scene.
Uses subprocess to avoid MuJoCo viewer segfaults when restarting.
"""

import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from neoscene.core.asset_catalog import AssetCatalog
from neoscene.core.scene_schema import SceneSpec
from neoscene.exporters.mjcf_exporter import scene_to_mjcf


@dataclass
class SceneSession:
    """A single scene editing session."""

    session_id: str
    last_scene: Optional[SceneSpec] = None
    viewer_process: Optional[subprocess.Popen] = None
    temp_xml_path: Optional[Path] = None


class SceneSessionManager:
    """Keeps track of scene sessions and manages MuJoCo viewers for each.

    MVP behavior: on each update, restart the viewer with the new scene.
    Uses subprocess to avoid segfaults when restarting viewers.
    """

    def __init__(self, asset_root: Path):
        """Initialize the session manager.

        Args:
            asset_root: Path to the assets directory.
        """
        self.asset_root = asset_root
        self.catalog = AssetCatalog(asset_root)
        self._sessions: Dict[str, SceneSession] = {}

    def get_or_create_session(self, session_id: Optional[str]) -> SceneSession:
        """Get existing session or create a new one.

        If session_id is None or unknown, create a new session with a fresh id.

        Args:
            session_id: Optional session ID to look up.

        Returns:
            Existing or new SceneSession.
        """
        if session_id is None or session_id not in self._sessions:
            new_id = session_id or self._generate_session_id()
            sess = SceneSession(session_id=new_id)
            self._sessions[new_id] = sess
            return sess
        return self._sessions[session_id]

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return str(uuid.uuid4())

    def _kill_viewer(self, session: SceneSession) -> None:
        """Kill the viewer process for a session."""
        if session.viewer_process and session.viewer_process.poll() is None:
            try:
                session.viewer_process.terminate()
                session.viewer_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                session.viewer_process.kill()
            except Exception:
                pass
        session.viewer_process = None

        # Clean up temp file
        if session.temp_xml_path and session.temp_xml_path.exists():
            try:
                session.temp_xml_path.unlink()
            except Exception:
                pass
        session.temp_xml_path = None

    def update_scene(self, session: SceneSession, scene: SceneSpec) -> None:
        """Store scene and (re)start the MuJoCo viewer for this session.

        MVP: stop existing viewer process (if any) and start a new one
        with the updated MJCF.

        Args:
            session: The session to update.
            scene: The new scene specification.
        """
        session.last_scene = scene

        # Kill old viewer
        self._kill_viewer(session)

        # Generate MJCF and write to temp file
        xml = scene_to_mjcf(scene, self.catalog)
        
        # Create a persistent temp file (won't be deleted on close)
        temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, prefix="neoscene_"
        )
        temp_file.write(xml)
        temp_file.close()
        session.temp_xml_path = Path(temp_file.name)

        # Launch viewer in subprocess
        # Using python -c to run a minimal script that loads and views the scene
        viewer_script = f'''
import mujoco
import mujoco.viewer
import time

model = mujoco.MjModel.from_xml_path("{session.temp_xml_path}")
data = mujoco.MjData(model)

with mujoco.viewer.launch_passive(model, data) as viewer:
    while viewer.is_running():
        mujoco.mj_step(model, data)
        viewer.sync()
        time.sleep(model.opt.timestep)
'''
        
        try:
            session.viewer_process = subprocess.Popen(
                ["python", "-c", viewer_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            # If subprocess fails, clean up
            self._kill_viewer(session)

    def describe_scene(self, session: SceneSession) -> dict:
        """Return a small dict summary of the current scene for frontend.

        Args:
            session: The session to describe.

        Returns:
            Dictionary with scene summary.
        """
        if not session.last_scene:
            return {"has_scene": False}

        spec = session.last_scene
        viewer_running = (
            session.viewer_process is not None 
            and session.viewer_process.poll() is None
        )
        
        return {
            "has_scene": True,
            "scene_name": spec.name,
            "environment_asset_id": spec.environment.asset_id,
            "object_count": len(spec.objects),
            "camera_count": len(spec.cameras),
            "viewer_running": viewer_running,
        }

    def cleanup(self) -> None:
        """Clean up all sessions and their viewers."""
        for session in self._sessions.values():
            self._kill_viewer(session)
        self._sessions.clear()
