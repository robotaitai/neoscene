"""Row Navigator: Autonomous orchard row-following for tractors.

This module implements a simple FSM-based controller for driving a tractor
through orchard rows, turning at the end, and entering the next row.

States:
- DRIVE_ROW: Follow the lane between trees
- TURN_AT_END: Execute U-turn when row ends
- ENTER_NEXT_ROW: Drive into next row until lane is detected
- DONE: Navigation complete
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Tuple

import numpy as np


class RowState(Enum):
    """Finite state machine states for row navigation."""
    DRIVE_ROW = auto()
    TURN_AT_END = auto()
    ENTER_NEXT_ROW = auto()
    DONE = auto()


@dataclass
class NavigatorConfig:
    """Configuration for the row navigator."""
    # Lane detection
    lane_lookahead: float = 15.0  # How far ahead to look for trees (m)
    lane_half_width: float = 2.5  # Expected half-width of lane (m)
    min_trees_per_side: int = 2   # Min trees to consider a "wall"
    
    # Driving
    v_nominal: float = 2.0        # Forward speed in lane (m/s)
    v_turn: float = 1.0           # Speed during turns (m/s)
    v_enter: float = 1.5          # Speed when entering row (m/s)
    
    # Controller gains
    Kp_lateral: float = 0.8       # Lateral correction gain
    Kp_yaw: float = 1.5           # Yaw correction gain
    
    # Turn parameters
    turn_radius: float = 4.0      # U-turn radius (m)
    row_spacing: float = 5.0      # Distance between rows (m)
    turn_time: float = 3.0        # Estimated turn duration (s)
    
    # Completion
    max_rows: int = 10            # Stop after this many rows
    lane_stable_steps: int = 10   # Steps to confirm lane detected


@dataclass
class NavigatorState:
    """Runtime state for the navigator."""
    current_state: RowState = RowState.DRIVE_ROW
    current_row: int = 0
    turn_direction: int = 1       # +1 = left, -1 = right
    state_timer: float = 0.0
    lane_stable_count: int = 0
    last_lateral_error: float = 0.0
    going_forward: bool = True    # True = +x direction, False = -x


class RowNavigator:
    """Autonomous row navigator for orchard tractors.
    
    Uses a finite state machine to:
    1. Drive along rows, staying centered between trees
    2. Detect end of row and execute U-turn
    3. Enter next row and repeat
    
    Example:
        navigator = RowNavigator(model, config)
        while running:
            v, omega = navigator.step(model, data, dt)
            # Apply v, omega to wheel motors
    """
    
    def __init__(self, model, config: Optional[NavigatorConfig] = None):
        """Initialize the navigator.
        
        Args:
            model: MuJoCo model (for body name lookups)
            config: Navigator configuration
        """
        import mujoco
        
        self.model = model
        self.config = config or NavigatorConfig()
        self.state = NavigatorState()
        self._mujoco = mujoco
        
        # Find tractor body
        self.tractor_body_id = self._find_body_containing("tractor_base")
        if self.tractor_body_id is None:
            self.tractor_body_id = self._find_body_containing("tractor")
        
        # Find tree bodies
        self.tree_body_ids = self._find_bodies_containing("tree")
        
        # Find motor actuators
        self.motor_ids = self._find_actuators_containing("motor")
        
    def _find_body_containing(self, substr: str) -> Optional[int]:
        """Find first body with name containing substr."""
        for b in range(self.model.nbody):
            name = self._mujoco.mj_id2name(
                self.model, self._mujoco.mjtObj.mjOBJ_BODY, b
            )
            if name and substr.lower() in name.lower():
                return b
        return None
    
    def _find_bodies_containing(self, substr: str) -> List[int]:
        """Find all bodies with names containing substr."""
        bodies = []
        for b in range(self.model.nbody):
            name = self._mujoco.mj_id2name(
                self.model, self._mujoco.mjtObj.mjOBJ_BODY, b
            )
            if name and substr.lower() in name.lower():
                bodies.append(b)
        return bodies
    
    def _find_actuators_containing(self, substr: str) -> List[int]:
        """Find actuators with names containing substr."""
        actuators = []
        for a in range(self.model.nu):
            name = self._mujoco.mj_id2name(
                self.model, self._mujoco.mjtObj.mjOBJ_ACTUATOR, a
            )
            if name and substr.lower() in name.lower():
                actuators.append(a)
        return actuators
    
    def get_robot_pose(self, data) -> Tuple[float, float, float]:
        """Get robot (x, y, yaw) in world frame."""
        if self.tractor_body_id is None:
            return 0.0, 0.0, 0.0
        
        pos = data.xpos[self.tractor_body_id]
        x, y = pos[0], pos[1]
        
        # Extract yaw from rotation matrix
        xmat = data.xmat[self.tractor_body_id].reshape(3, 3)
        yaw = np.arctan2(xmat[1, 0], xmat[0, 0])
        
        return x, y, yaw
    
    def get_tree_positions(self, data) -> List[Tuple[float, float]]:
        """Get all tree positions in world frame."""
        positions = []
        for body_id in self.tree_body_ids:
            pos = data.xpos[body_id]
            positions.append((pos[0], pos[1]))
        return positions
    
    def world_to_robot(
        self, px: float, py: float, 
        robot_x: float, robot_y: float, robot_yaw: float
    ) -> Tuple[float, float]:
        """Transform world point to robot frame.
        
        Returns (x_forward, y_left) in robot coordinates.
        """
        dx = px - robot_x
        dy = py - robot_y
        c = np.cos(-robot_yaw)
        s = np.sin(-robot_yaw)
        x_rel = c * dx - s * dy
        y_rel = s * dx + c * dy
        return x_rel, y_rel
    
    def detect_lane(
        self, data
    ) -> Tuple[bool, bool, float]:
        """Detect lane from tree positions.
        
        Returns:
            (has_left_wall, has_right_wall, lateral_error)
        """
        robot_x, robot_y, robot_yaw = self.get_robot_pose(data)
        tree_positions = self.get_tree_positions(data)
        
        cfg = self.config
        
        # Transform trees to robot frame and filter to front
        front_trees = []
        for (px, py) in tree_positions:
            xf, yf = self.world_to_robot(px, py, robot_x, robot_y, robot_yaw)
            if 0 < xf < cfg.lane_lookahead:
                front_trees.append((xf, yf))
        
        # Separate left and right walls
        left_trees = [(xf, yf) for (xf, yf) in front_trees 
                      if 0 < yf < cfg.lane_half_width * 2]
        right_trees = [(xf, yf) for (xf, yf) in front_trees 
                       if -cfg.lane_half_width * 2 < yf < 0]
        
        has_left = len(left_trees) >= cfg.min_trees_per_side
        has_right = len(right_trees) >= cfg.min_trees_per_side
        
        # Compute lateral error (how far off center)
        lateral_error = 0.0
        if has_left and has_right:
            y_left_avg = np.mean([yf for _, yf in left_trees])
            y_right_avg = np.mean([yf for _, yf in right_trees])
            lateral_error = 0.5 * (y_left_avg + y_right_avg)
        elif has_left:
            # Only left wall - we're probably too far right
            lateral_error = 0.5  # Nudge left
        elif has_right:
            # Only right wall - we're probably too far left
            lateral_error = -0.5  # Nudge right
        
        return has_left, has_right, lateral_error
    
    def step(self, model, data, dt: float) -> Tuple[float, float]:
        """Execute one step of the navigator.
        
        Args:
            model: MuJoCo model
            data: MuJoCo data
            dt: Time step
            
        Returns:
            (v, omega): Linear and angular velocity commands
        """
        state = self.state
        cfg = self.config
        
        # Get perception
        has_left, has_right, lateral_error = self.detect_lane(data)
        robot_x, robot_y, robot_yaw = self.get_robot_pose(data)
        
        state.last_lateral_error = lateral_error
        state.state_timer += dt
        
        # State machine
        if state.current_state == RowState.DRIVE_ROW:
            v, omega = self._drive_row(
                has_left, has_right, lateral_error, robot_yaw
            )
            
            # Check for end of row
            if not has_left and not has_right:
                state.lane_stable_count = 0
                state.current_state = RowState.TURN_AT_END
                state.state_timer = 0.0
                
        elif state.current_state == RowState.TURN_AT_END:
            v, omega = self._turn_at_end()
            
            # Check if turn is complete
            if state.state_timer > cfg.turn_time:
                state.current_state = RowState.ENTER_NEXT_ROW
                state.state_timer = 0.0
                state.current_row += 1
                state.turn_direction *= -1  # Alternate turn direction
                state.going_forward = not state.going_forward
                
                if state.current_row >= cfg.max_rows:
                    state.current_state = RowState.DONE
                    
        elif state.current_state == RowState.ENTER_NEXT_ROW:
            v, omega = self._enter_next_row(
                has_left, has_right, lateral_error, robot_yaw
            )
            
            # Check if lane is stable
            if has_left and has_right:
                state.lane_stable_count += 1
                if state.lane_stable_count >= cfg.lane_stable_steps:
                    state.current_state = RowState.DRIVE_ROW
                    state.lane_stable_count = 0
            else:
                state.lane_stable_count = 0
                
        else:  # DONE
            v, omega = 0.0, 0.0
        
        return v, omega
    
    def _drive_row(
        self, has_left: bool, has_right: bool, 
        lateral_error: float, robot_yaw: float
    ) -> Tuple[float, float]:
        """Controller for DRIVE_ROW state."""
        cfg = self.config
        state = self.state
        
        # Desired yaw: 0 when going forward, pi when going backward
        if state.going_forward:
            desired_yaw = 0.0
        else:
            desired_yaw = np.pi
        
        # Yaw error (wrapped to -pi..pi)
        yaw_error = desired_yaw - robot_yaw
        yaw_error = np.arctan2(np.sin(yaw_error), np.cos(yaw_error))
        
        # Control law
        omega = -cfg.Kp_lateral * lateral_error - cfg.Kp_yaw * yaw_error
        v = cfg.v_nominal
        
        return v, omega
    
    def _turn_at_end(self) -> Tuple[float, float]:
        """Controller for TURN_AT_END state."""
        cfg = self.config
        state = self.state
        
        # Curved path: omega = v / R
        v = cfg.v_turn
        omega = state.turn_direction * v / cfg.turn_radius
        
        return v, omega
    
    def _enter_next_row(
        self, has_left: bool, has_right: bool,
        lateral_error: float, robot_yaw: float
    ) -> Tuple[float, float]:
        """Controller for ENTER_NEXT_ROW state."""
        cfg = self.config
        state = self.state
        
        # Desired yaw (opposite direction now)
        if state.going_forward:
            desired_yaw = 0.0
        else:
            desired_yaw = np.pi
        
        yaw_error = desired_yaw - robot_yaw
        yaw_error = np.arctan2(np.sin(yaw_error), np.cos(yaw_error))
        
        # Gentle correction while entering
        omega = -cfg.Kp_lateral * lateral_error * 0.5 - cfg.Kp_yaw * yaw_error
        v = cfg.v_enter
        
        return v, omega
    
    def apply_controls(self, data, v: float, omega: float, wheelbase: float = 1.5):
        """Apply velocity commands to wheel motors.
        
        Args:
            data: MuJoCo data
            v: Linear velocity (m/s)
            omega: Angular velocity (rad/s)
            wheelbase: Distance between wheels (m)
        """
        # Differential drive kinematics
        v_left = v - 0.5 * wheelbase * omega
        v_right = v + 0.5 * wheelbase * omega
        
        # Apply to motors (assuming velocity-controlled)
        for i, motor_id in enumerate(self.motor_ids):
            if i % 2 == 0:  # Left motors
                data.ctrl[motor_id] = v_left
            else:           # Right motors
                data.ctrl[motor_id] = v_right
    
    def get_status(self) -> dict:
        """Get navigator status for UI display."""
        return {
            "state": self.state.current_state.name,
            "row": self.state.current_row,
            "turn_direction": "left" if self.state.turn_direction > 0 else "right",
            "lateral_error": round(self.state.last_lateral_error, 3),
            "going_forward": self.state.going_forward,
        }

