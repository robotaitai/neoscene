"""Scene Session Manager - tracks scene sessions and manages MuJoCo viewers.

MVP behavior: on each update, restart the viewer with the new scene.
Later, you can optimize to implement graceful reload.
"""

import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from neoscene.core.asset_catalog import AssetCatalog
from neoscene.core.scene_schema import SceneSpec
from neoscene.exporters.mjcf_exporter import scene_to_mjcf
from neoscene.backends.mujoco_runner import run_mjcf_xml


@dataclass
class SceneSession:
    """A single scene editing session."""

    session_id: str
    last_scene: Optional[SceneSpec] = None
    viewer_thread: Optional[threading.Thread] = None
    # Simple flag to stop/restart viewer loops later if needed
    stop_flag: bool = False


class SceneSessionManager:
    """Keeps track of scene sessions and manages MuJoCo viewers for each.

    MVP behavior: on each update, restart the viewer with the new scene.
    """

    def __init__(self, asset_root: Path):
        """Initialize the session manager.

        Args:
            asset_root: Path to the assets directory.
        """
        self.asset_root = asset_root
        self.catalog = AssetCatalog(asset_root)
        self._sessions: Dict[str, SceneSession] = {}
        self._lock = threading.Lock()

    def get_or_create_session(self, session_id: Optional[str]) -> SceneSession:
        """Get existing session or create a new one.

        If session_id is None or unknown, create a new session with a fresh id.

        Args:
            session_id: Optional session ID to look up.

        Returns:
            Existing or new SceneSession.
        """
        with self._lock:
            if session_id is None or session_id not in self._sessions:
                new_id = session_id or self._generate_session_id()
                sess = SceneSession(session_id=new_id)
                self._sessions[new_id] = sess
                return sess
            return self._sessions[session_id]

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return str(uuid.uuid4())

    def update_scene(self, session: SceneSession, scene: SceneSpec):
        """Store scene and (re)start the MuJoCo viewer for this session.

        MVP: stop existing viewer thread (if any) and start a new one
        with the updated MJCF.

        Args:
            session: The session to update.
            scene: The new scene specification.
        """
        with self._lock:
            session.last_scene = scene

            # Stop old viewer if exists
            if session.viewer_thread and session.viewer_thread.is_alive():
                # Set a flag; your viewer loop can check this flag to exit.
                session.stop_flag = True
                # We don't necessarily join here to avoid blocking.

            # Start new viewer with the new scene
            session.stop_flag = False
            xml = scene_to_mjcf(scene, self.catalog)

            def _run_viewer():
                # For MVP we ignore stop_flag inside run_mjcf_xml.
                # Later, you can add stop logic there.
                try:
                    run_mjcf_xml(xml)
                except Exception:
                    # Viewer closed or failed - that's OK
                    pass

            t = threading.Thread(target=_run_viewer, daemon=True)
            session.viewer_thread = t
            t.start()

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
        return {
            "has_scene": True,
            "scene_name": spec.name,
            "environment_asset_id": spec.environment.asset_id,
            "object_count": len(spec.objects),
            "camera_count": len(spec.cameras),
        }

