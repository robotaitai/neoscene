"""Scene Session Manager - tracks scene sessions and manages MuJoCo viewers.

MVP behavior: on each update, restart the viewer with the new scene.
Uses subprocess to avoid MuJoCo viewer segfaults when restarting.
Also runs a headless simulation worker for sensor/camera data.
"""

import os
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import numpy as np

from neoscene.core.asset_catalog import AssetCatalog
from neoscene.core.logging_config import get_logger
from neoscene.core.scene_schema import SceneSpec
from neoscene.exporters.mjcf_exporter import scene_to_mjcf

logger = get_logger(__name__)

# Use EGL for GPU rendering, fall back to OSMesa for software rendering
os.environ.setdefault("MUJOCO_GL", "egl")


@dataclass
class SimulationWorker:
    """Headless simulation worker that runs MuJoCo and collects sensor/camera data."""
    
    xml_path: str
    running: bool = False
    latest_sensors: dict = field(default_factory=dict)
    latest_image: Optional[np.ndarray] = None
    navigator_status: dict = field(default_factory=dict)
    task_status: dict = field(default_factory=dict)
    _model: object = None
    _data: object = None
    _renderer: object = None
    _render_error_logged: bool = False
    _navigator: object = None  # RowNavigator when in orchard mode
    _task_runner: object = None  # TaskRunner for path following
    
    def start(self):
        """Initialize MuJoCo model and data."""
        import mujoco
        self._model = mujoco.MjModel.from_xml_path(self.xml_path)
        self._data = mujoco.MjData(self._model)
        self.running = True
        
        # Initialize TaskRunner for path following
        self._init_task_runner()
        
        # Check if we have trees - if so, enable row navigator (fallback when no task)
        self._init_navigator()
        
        logger.info(f"SimWorker started: ncam={self._model.ncam}, nsensor={self._model.nsensor}, navigator={'active' if self._navigator else 'off'}, task_runner={'ready' if self._task_runner else 'off'}")
    
    def _init_task_runner(self):
        """Initialize TaskRunner for path-following tasks."""
        try:
            from neoscene.backends.task_runner import TaskRunner
            self._task_runner = TaskRunner(self._model, self._data)
            logger.debug("TaskRunner initialized")
        except Exception as e:
            logger.warning(f"Failed to init TaskRunner: {e}")
            self._task_runner = None
    
    def set_scene(self, scene: SceneSpec):
        """Update the scene reference for the task runner."""
        if self._task_runner:
            self._task_runner.set_scene(scene)
    
    def start_task(self, task_name: str) -> bool:
        """Start a task by name. Returns True if successful."""
        if self._task_runner:
            return self._task_runner.start_task(task_name)
        return False
    
    def stop_task(self):
        """Stop the currently active task."""
        if self._task_runner:
            self._task_runner.stop_task()
    
    def get_task_status(self) -> dict:
        """Get current task execution status."""
        if self._task_runner:
            return self._task_runner.get_status()
        return {"active": False}
    
    def _init_navigator(self):
        """Initialize row navigator if trees are present."""
        import mujoco
        
        # Check for tree bodies
        has_trees = False
        for b in range(self._model.nbody):
            name = mujoco.mj_id2name(self._model, mujoco.mjtObj.mjOBJ_BODY, b)
            if name and 'tree' in name.lower():
                has_trees = True
                break
        
        if has_trees:
            try:
                from neoscene.core.row_navigator import RowNavigator, NavigatorConfig
                config = NavigatorConfig()
                self._navigator = RowNavigator(self._model, config)
                logger.info(f"RowNavigator enabled with {len(self._navigator.tree_body_ids)} trees")
            except Exception as e:
                logger.warning(f"Failed to init RowNavigator: {e}")
                self._navigator = None
    
    def loop(self):
        """Main simulation loop - runs at ~50Hz."""
        import mujoco
        
        try:
            self.start()
        except Exception as e:
            logger.error(f"SimWorker failed to start: {e}")
            return
        
        while self.running:
            try:
                self._apply_controls()
                mujoco.mj_step(self._model, self._data)
                self._read_sensors()
                self._render_camera()
                time.sleep(0.02)  # 50 Hz
            except Exception as e:
                logger.error(f"SimWorker loop error: {e}")
                break
        
        logger.info("SimWorker stopped")
    
    def _apply_controls(self):
        """Apply control inputs to actuators for motion.
        
        Priority:
        1. If TaskRunner has an active task: use TaskRunner controls
        2. Else if RowNavigator is active: use autonomous navigation
        3. Otherwise: simple demo motion for wheels
        
        Human walking gait is always applied separately.
        """
        import mujoco
        import math
        
        m = self._model
        d = self._data
        dt = m.opt.timestep
        t = d.time
        
        tractor_controlled = False
        
        # Priority 1: TaskRunner (user-triggered path following)
        if self._task_runner is not None and self._task_runner.is_active():
            self._task_runner.step(dt)
            self.task_status = self._task_runner.get_status()
            tractor_controlled = True
        else:
            self.task_status = {"active": False}
        
        # Priority 2: RowNavigator (autonomous orchard navigation, when no task)
        if not tractor_controlled and self._navigator is not None:
            v, omega = self._navigator.step(m, d, dt)
            # Apply controls manually
            wheelbase = 1.5
            v_left = v - 0.5 * wheelbase * omega
            v_right = v + 0.5 * wheelbase * omega
            
            # Find and set motor controls
            for i in range(m.nu):
                name = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_ACTUATOR, i)
                if not name:
                    continue
                name_lower = name.lower()
                
                if 'motor' in name_lower:
                    # Left motors (rl = rear left)
                    if '_rl' in name_lower:
                        d.ctrl[i] = v_left
                    # Right motors (rr = rear right)
                    elif '_rr' in name_lower:
                        d.ctrl[i] = v_right
            
            self.navigator_status = self._navigator.get_status()
            tractor_controlled = True
        
        # Priority 3: Fallback - simple forward motion if no other controller
        if not tractor_controlled:
            for i in range(m.nu):
                name = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_ACTUATOR, i)
                if not name:
                    continue
                name_lower = name.lower()
                
                if 'motor' in name_lower or 'drive' in name_lower:
                    d.ctrl[i] = 2.0  # Forward at ~1 m/s
        
        # Human walking gait (always active for any humans)
        for i in range(m.nu):
            name = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_ACTUATOR, i)
            if not name:
                continue
            name_lower = name.lower()
            
            if 'hip_ctrl' in name_lower:
                phase = 0 if 'left' in name_lower else math.pi
                d.ctrl[i] = 20.0 * math.sin(2.0 * t + phase)
            elif 'knee_ctrl' in name_lower:
                phase = 0 if 'left' in name_lower else math.pi
                d.ctrl[i] = 30.0 * max(0, math.sin(2.0 * t + phase))
            elif 'shoulder_ctrl' in name_lower:
                phase = math.pi if 'left' in name_lower else 0
                d.ctrl[i] = 15.0 * math.sin(2.0 * t + phase)
    
    def _read_sensors(self):
        """Read all sensor values from the simulation."""
        import mujoco
        
        m = self._model
        d = self._data
        sensors = {}
        
        for sid in range(m.nsensor):
            name = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_SENSOR, sid)
            if name is None:
                name = f"sensor_{sid}"
            # Get sensor dimension and address
            dim = m.sensor_dim[sid]
            start = m.sensor_adr[sid]
            
            if dim == 1:
                sensors[name] = float(d.sensordata[start])
            else:
                sensors[name] = [float(d.sensordata[start + i]) for i in range(dim)]
        
        # Add task status if active
        if self._task_runner is not None and self.task_status.get("active"):
            ts = self.task_status
            sensors["_task_name"] = ts.get("task_name", "")
            sensors["_task_waypoint"] = f"{ts.get('waypoint_index', 0)}/{ts.get('total_waypoints', 0)}"
            sensors["_task_distance"] = ts.get("distance_traveled", 0.0)
        elif self._navigator is not None:
            # Fallback to navigator status if no task active
            nav = self.navigator_status
            sensors["_nav_state"] = nav.get("state", "OFF")
            sensors["_nav_row"] = nav.get("row", 0)
            sensors["_nav_lateral_error"] = nav.get("lateral_error", 0.0)
        
        self.latest_sensors = sensors
    
    def _render_camera(self):
        """Render camera view to image (if cameras exist)."""
        import mujoco
        
        m = self._model
        d = self._data
        
        # Check if there are any cameras
        if m.ncam == 0:
            return
        
        # Find the best camera to use (prefer vehicle-mounted cameras)
        camera_idx = 0
        for i in range(m.ncam):
            name = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_CAMERA, i)
            if name and ('driver' in name.lower() or 'rear' in name.lower()):
                camera_idx = i
                break
        
        # Initialize renderer if needed
        if self._renderer is None:
            try:
                self._renderer = mujoco.Renderer(m, height=240, width=320)
                cam_name = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_CAMERA, camera_idx)
                logger.info(f"Camera renderer: using '{cam_name}' ({m.ncam} total)")
            except Exception as e:
                if not self._render_error_logged:
                    logger.warning(f"Could not create camera renderer: {e}")
                    self._render_error_logged = True
                return
        
        try:
            # Update scene and render
            self._renderer.update_scene(d, camera=camera_idx)
            self.latest_image = self._renderer.render()
        except Exception as e:
            if not self._render_error_logged:
                logger.warning(f"Camera render error: {e}")
                self._render_error_logged = True
    
    def stop(self):
        """Stop the simulation loop."""
        self.running = False
        if self._renderer is not None:
            try:
                self._renderer.close()
            except Exception:
                pass
            self._renderer = None


@dataclass
class SceneSession:
    """A single scene editing session."""

    session_id: str
    last_scene: Optional[SceneSpec] = None
    viewer_process: Optional[subprocess.Popen] = None
    temp_xml_path: Optional[Path] = None
    sim_worker: Optional[SimulationWorker] = None
    sim_thread: Optional[threading.Thread] = None


class SceneSessionManager:
    """Keeps track of scene sessions and manages MuJoCo viewers for each.

    MVP behavior: on each update, restart the viewer with the new scene.
    Uses subprocess to avoid segfaults when restarting viewers.
    Also starts a headless simulation worker for sensor/camera polling.
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
    
    def get_session(self, session_id: str) -> Optional[SceneSession]:
        """Get a session by ID without creating a new one."""
        return self._sessions.get(session_id)

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
    
    def _stop_sim_worker(self, session: SceneSession) -> None:
        """Stop the simulation worker for a session."""
        if session.sim_worker:
            session.sim_worker.stop()
        if session.sim_thread and session.sim_thread.is_alive():
            session.sim_thread.join(timeout=1)
        session.sim_worker = None
        session.sim_thread = None

    def _cleanup_temp_file(self, session: SceneSession) -> None:
        """Clean up temp XML file."""
        if session.temp_xml_path and session.temp_xml_path.exists():
            try:
                session.temp_xml_path.unlink()
            except Exception:
                pass
        session.temp_xml_path = None

    def update_scene(self, session: SceneSession, scene: SceneSpec) -> None:
        """Store scene and (re)start the MuJoCo viewer for this session.

        Also starts a headless simulation worker for sensor/camera data.

        Args:
            session: The session to update.
            scene: The new scene specification.
        """
        session.last_scene = scene

        # Kill old viewer and sim worker
        self._kill_viewer(session)
        self._stop_sim_worker(session)
        self._cleanup_temp_file(session)

        # Generate MJCF and write to temp file
        xml = scene_to_mjcf(scene, self.catalog)
        
        # Create a persistent temp file (won't be deleted on close)
        temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, prefix="neoscene_"
        )
        temp_file.write(xml)
        temp_file.close()
        session.temp_xml_path = Path(temp_file.name)

        # 1) Launch viewer in subprocess with UI hidden by default
        viewer_script = f'''
import mujoco
import mujoco.viewer
import time

model = mujoco.MjModel.from_xml_path("{session.temp_xml_path}")
data = mujoco.MjData(model)

with mujoco.viewer.launch_passive(model, data) as viewer:
    # Hide the UI panels (equivalent to pressing Tab)
    viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_COM] = False
    viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_JOINT] = False
    
    # Set a nicer camera position
    viewer.cam.azimuth = -45
    viewer.cam.elevation = -25
    viewer.cam.distance = 30
    viewer.cam.lookat[:] = [10, 10, 0]
    
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
            pass

        # 2) Start headless simulation worker for sensors/cameras
        try:
            worker = SimulationWorker(xml_path=str(session.temp_xml_path))
            sim_thread = threading.Thread(target=worker.loop, daemon=True)
            session.sim_worker = worker
            session.sim_thread = sim_thread
            sim_thread.start()
            
            # Give worker time to initialize, then set scene for TaskRunner
            time.sleep(0.2)
            if session.sim_worker and session.sim_worker.running:
                session.sim_worker.set_scene(scene)
        except Exception as e:
            logger.warning(f"Failed to start sim worker: {e}")

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
        sim_running = (
            session.sim_worker is not None 
            and session.sim_worker.running
        )
        
        return {
            "has_scene": True,
            "scene_name": spec.name,
            "environment_asset_id": spec.environment.asset_id,
            "object_count": len(spec.objects),
            "camera_count": len(spec.cameras),
            "viewer_running": viewer_running,
            "sim_running": sim_running,
        }
    
    def get_sensors(self, session_id: str) -> dict:
        """Get latest sensor values for a session.
        
        Returns:
            Dict with 'ok' boolean and 'sensors' dict.
        """
        session = self.get_session(session_id)
        if not session or not session.sim_worker:
            return {"ok": False, "sensors": {}}
        return {"ok": True, "sensors": session.sim_worker.latest_sensors}
    
    def get_camera_image(self, session_id: str) -> Optional[np.ndarray]:
        """Get latest camera image for a session.
        
        Returns:
            Numpy array (RGB image) or None if not available.
        """
        session = self.get_session(session_id)
        if not session or not session.sim_worker:
            return None
        return session.sim_worker.latest_image
    
    def start_task(self, session_id: str, task_name: str) -> bool:
        """Start a task by name for a session.
        
        Args:
            session_id: The session ID.
            task_name: Name of the task to start.
            
        Returns:
            True if task was started successfully, False otherwise.
        """
        session = self.get_session(session_id)
        if not session or not session.sim_worker or not session.last_scene:
            return False
        
        # Ensure TaskRunner has the current scene
        session.sim_worker.set_scene(session.last_scene)
        return session.sim_worker.start_task(task_name)
    
    def stop_task(self, session_id: str) -> None:
        """Stop the active task for a session."""
        session = self.get_session(session_id)
        if session and session.sim_worker:
            session.sim_worker.stop_task()
    
    def get_task_status(self, session_id: str) -> dict:
        """Get current task status for a session."""
        session = self.get_session(session_id)
        if not session or not session.sim_worker:
            return {"active": False}
        return session.sim_worker.get_task_status()

    def cleanup(self) -> None:
        """Clean up all sessions and their viewers."""
        for session in self._sessions.values():
            self._kill_viewer(session)
            self._stop_sim_worker(session)
            self._cleanup_temp_file(session)
        self._sessions.clear()
