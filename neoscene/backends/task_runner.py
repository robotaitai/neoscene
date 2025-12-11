# neoscene/backends/task_runner.py
"""
Task execution engine for path-following behaviors.

Manages execution of path_follow tasks, converting waypoint paths into
differential drive commands for the tractor.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
import logging

import numpy as np
import mujoco

from neoscene.core.scene_schema import SceneSpec, PathSpec, TaskSpec

logger = logging.getLogger(__name__)


@dataclass
class ActiveTask:
    """State for a currently executing task."""
    task: TaskSpec
    path: PathSpec
    lookahead: float = 3.0
    current_index: int = 0
    finished: bool = False
    distance_traveled: float = 0.0
    last_position: Tuple[float, float] = field(default_factory=lambda: (0.0, 0.0))


class TaskRunner:
    """
    Manages execution of a single active path_follow task.
    
    Uses pure pursuit algorithm to follow waypoint paths.
    """

    def __init__(self, model: mujoco.MjModel, data: mujoco.MjData):
        self.model = model
        self.data = data
        self.scene: Optional[SceneSpec] = None
        self.active: Optional[ActiveTask] = None
        
        # Robot configuration (will be auto-detected)
        self._body_id: Optional[int] = None
        self._left_motor_id: Optional[int] = None
        self._right_motor_id: Optional[int] = None
        self._wheelbase: float = 2.0
        
        # Control parameters
        self.lookahead_distance: float = 3.0
        self.finish_threshold: float = 1.5  # meters from final waypoint
        
        self._detect_robot()

    def _detect_robot(self):
        """Auto-detect tractor body and actuators."""
        m = self.model
        
        # Find tractor body (look for patterns)
        for i in range(m.nbody):
            name = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, i)
            if name and ("tractor" in name.lower() and "base" in name.lower()):
                self._body_id = i
                logger.info(f"TaskRunner: found robot body '{name}' (id={i})")
                break
        
        if self._body_id is None:
            logger.warning("TaskRunner: no tractor body found")
            return
        
        # Find wheel actuators - look for motor_rl/motor_rr patterns (common in tractors)
        # Also check for left/right, _fl/_fr, _rl/_rr suffixes
        for i in range(m.nu):
            name = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_ACTUATOR, i)
            if name:
                name_lower = name.lower()
                
                # Left wheel motor patterns
                is_left = ("motor_rl" in name_lower or 
                          "motor_fl" in name_lower or 
                          "_rl" in name_lower or 
                          "_fl" in name_lower or
                          "left" in name_lower)
                
                # Right wheel motor patterns
                is_right = ("motor_rr" in name_lower or 
                           "motor_fr" in name_lower or 
                           "_rr" in name_lower or 
                           "_fr" in name_lower or
                           "right" in name_lower)
                
                if is_left and self._left_motor_id is None:
                    self._left_motor_id = i
                    logger.info(f"TaskRunner: left motor '{name}' (id={i})")
                elif is_right and self._right_motor_id is None:
                    self._right_motor_id = i
                    logger.info(f"TaskRunner: right motor '{name}' (id={i})")
        
        if self._left_motor_id is None or self._right_motor_id is None:
            logger.warning(f"TaskRunner: motors not fully detected (left={self._left_motor_id}, right={self._right_motor_id})")

    def set_scene(self, scene: SceneSpec):
        """Update the scene reference (called when SceneSpec changes)."""
        self.scene = scene
        logger.debug(f"TaskRunner: scene set with {len(scene.paths)} paths, {len(scene.tasks)} tasks")

    def start_task(self, task_name: str) -> bool:
        """
        Start executing a task by name.
        
        Returns True if task was found and started, False otherwise.
        """
        if self.scene is None:
            logger.warning("TaskRunner: no scene set")
            return False
        
        if self._body_id is None:
            logger.warning("TaskRunner: no robot body detected")
            return False
        
        if self._left_motor_id is None or self._right_motor_id is None:
            logger.warning(f"TaskRunner: motors not detected (L={self._left_motor_id}, R={self._right_motor_id})")
            return False

        # Find the task
        task = next((t for t in self.scene.tasks if t.name == task_name), None)
        if not task:
            logger.warning(f"TaskRunner: task '{task_name}' not found in {[t.name for t in self.scene.tasks]}")
            return False

        # Find the path referenced by the task
        path = next((p for p in self.scene.paths if p.name == task.path_name), None)
        if not path:
            logger.warning(f"TaskRunner: path '{task.path_name}' not found for task '{task_name}'")
            return False

        if len(path.waypoints) < 2:
            logger.warning(f"TaskRunner: path '{path.name}' has fewer than 2 waypoints")
            return False

        # Get current position for tracking
        x, y, _ = self._get_pose()
        
        self.active = ActiveTask(
            task=task,
            path=path,
            lookahead=self.lookahead_distance,
            current_index=0,
            finished=False,
            distance_traveled=0.0,
            last_position=(x, y),
        )
        
        logger.info(f"TaskRunner: started task '{task_name}' on path '{path.name}' ({len(path.waypoints)} waypoints)")
        return True

    def stop_task(self):
        """Stop the currently active task."""
        if self.active:
            logger.info(f"TaskRunner: stopped task '{self.active.task.name}'")
        self.active = None
        
        # Zero the controls
        if self._left_motor_id is not None:
            self.data.ctrl[self._left_motor_id] = 0.0
        if self._right_motor_id is not None:
            self.data.ctrl[self._right_motor_id] = 0.0

    def is_active(self) -> bool:
        """Check if a task is currently running."""
        return self.active is not None and not self.active.finished

    def get_status(self) -> dict:
        """Get current task execution status."""
        if not self.active:
            return {"active": False}
        
        return {
            "active": True,
            "task_name": self.active.task.name,
            "path_name": self.active.path.name,
            "waypoint_index": self.active.current_index,
            "total_waypoints": len(self.active.path.waypoints),
            "distance_traveled": round(self.active.distance_traveled, 2),
            "finished": self.active.finished,
        }

    def _get_pose(self) -> Tuple[float, float, float]:
        """Get robot position (x, y) and yaw angle."""
        if self._body_id is None:
            return 0.0, 0.0, 0.0
        
        x, y, _ = self.data.xpos[self._body_id]
        # Extract yaw from body rotation matrix
        m = self.data.xmat[self._body_id].reshape(3, 3)
        yaw = np.arctan2(m[1, 0], m[0, 0])
        return float(x), float(y), float(yaw)

    def _path_points(self) -> List[Tuple[float, float]]:
        """Get waypoints as (x, y) tuples."""
        if not self.active:
            return []
        return [(wp.x, wp.y) for wp in self.active.path.waypoints]

    def _find_target(self, x: float, y: float) -> Tuple[float, float, int]:
        """
        Find the target point on the path using lookahead.
        
        Returns (target_x, target_y, target_index).
        """
        pts = self._path_points()
        if len(pts) == 0:
            return x, y, 0

        # Find closest point on path
        dists = [np.hypot(px - x, py - y) for (px, py) in pts]
        closest_idx = int(np.argmin(dists))

        # March forward along path until we accumulate lookahead distance
        L = self.active.lookahead
        accum = 0.0
        target_idx = closest_idx
        
        while target_idx < len(pts) - 1 and accum < L:
            p0 = pts[target_idx]
            p1 = pts[target_idx + 1]
            seg_len = np.hypot(p1[0] - p0[0], p1[1] - p0[1])
            accum += seg_len
            target_idx += 1

        return pts[target_idx][0], pts[target_idx][1], target_idx

    def step(self, dt: float):
        """
        Execute one control step.
        
        Should be called before mj_step() in the simulation loop.
        """
        if not self.active or self.active.finished:
            return

        if self._body_id is None or self._left_motor_id is None or self._right_motor_id is None:
            return

        # Get current pose
        x, y, yaw = self._get_pose()
        
        # Update distance traveled
        dx = x - self.active.last_position[0]
        dy = y - self.active.last_position[1]
        self.active.distance_traveled += np.hypot(dx, dy)
        self.active.last_position = (x, y)

        # Find target point
        xt, yt, target_idx = self._find_target(x, y)
        self.active.current_index = target_idx

        # Transform target to robot frame
        dx = xt - x
        dy = yt - y
        c = np.cos(-yaw)
        s = np.sin(-yaw)
        x_robot = c * dx - s * dy
        y_robot = s * dx + c * dy

        # Pure pursuit: compute curvature
        Ld = max(np.hypot(x_robot, y_robot), 0.1)
        kappa = 2.0 * y_robot / (Ld * Ld)

        # Get speed from task
        v = self.active.task.speed

        # Convert (v, kappa) to differential wheel velocities
        v_left = v * (1.0 - kappa * self._wheelbase / 2.0)
        v_right = v * (1.0 + kappa * self._wheelbase / 2.0)

        # Clamp wheel speeds
        max_speed = 5.0
        v_left = np.clip(v_left, -max_speed, max_speed)
        v_right = np.clip(v_right, -max_speed, max_speed)

        # Apply to actuators
        self.data.ctrl[self._left_motor_id] = v_left
        self.data.ctrl[self._right_motor_id] = v_right

        # Check if finished
        pts = self._path_points()
        final_x, final_y = pts[-1]
        dist_to_end = np.hypot(x - final_x, y - final_y)
        
        at_end = target_idx >= len(pts) - 1 and dist_to_end < self.finish_threshold

        if at_end:
            if self.active.path.loop or self.active.task.repeat:
                # Reset to beginning of path
                self.active.current_index = 0
                logger.info(f"TaskRunner: task '{self.active.task.name}' looping")
            else:
                # Task complete
                self.active.finished = True
                self.stop_task()
                logger.info(f"TaskRunner: task '{self.active.task.name}' finished")

