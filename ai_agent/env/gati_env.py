from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from typing import Any, Optional

import gymnasium as gym
import numpy as np
from gymnasium import spaces


@dataclass
class BridgeConfig:
    host: str = "127.0.0.1"
    port: int = 6969
    timeout_seconds: float = 15.0


class GatiEnv(gym.Env):
    """Gymnasium wrapper around the Gati bridge socket protocol.

    Observations are normalized:
      - xPos: relative to start (offset from initial position)
      - yPos: relative to ground level (~105)
      - xVel: player speed multiplier (typically 8.4)
      - yVel: vertical velocity (clipped)
      - rotation: normalized to [-180, 180]
      - isGrounded: 0/1
      - isDead: 0/1
      - hasWon: 0/1
      - rays[0..4]: normalized to [0, 1] (0 = touching, 1 = far)
    """

    metadata = {"render_modes": []}
    NUM_RAYS = 5
    GROUND_Y = 105.0
    PLAYER_SPEED_NORM = 8.4
    MAX_Y_VEL = 20.0

    def __init__(self, host: str = "127.0.0.1", port: int = 6969, timeout_seconds: float = 15.0) -> None:
        super().__init__()
        self.config = BridgeConfig(host=host, port=port, timeout_seconds=timeout_seconds)
        self.action_space = spaces.Discrete(2)
        obs_size = 8 + self.NUM_RAYS
        self.observation_space = spaces.Box(low=-1.0, high=1.0, shape=(obs_size,), dtype=np.float32)
        self._socket: Optional[socket.socket] = None
        self._receive_buffer = ""
        self._start_x: float = 0.0
        self._last_observation = np.zeros(obs_size, dtype=np.float32)
        self._step_count: int = 0
        self._episode_reward: float = 0.0

    def _connect(self) -> None:
        if self._socket is not None:
            return

        try:
            connection = socket.create_connection(
                (self.config.host, self.config.port),
                timeout=self.config.timeout_seconds,
            )
        except (ConnectionRefusedError, TimeoutError, OSError) as error:
            raise ConnectionError(
                f"Could not connect to Gati-bridge at {self.config.host}:{self.config.port}. "
                "Please make sure Geometry Dash is running, the axzyte.gati-bridge mod is loaded, "
                "and Level 1 is open."
            ) from error

        connection.settimeout(self.config.timeout_seconds)
        self._socket = connection

    def _send_message(self, payload: dict[str, Any]) -> None:
        self._connect()
        assert self._socket is not None
        message = json.dumps(payload, separators=(",", ":")) + "\n"
        self._socket.sendall(message.encode("utf-8"))

    def _receive_message(self) -> dict[str, Any]:
        self._connect()
        assert self._socket is not None

        try:
            while "\n" not in self._receive_buffer:
                chunk = self._socket.recv(4096)
                if not chunk:
                    raise ConnectionError("The bridge closed the connection.")
                self._receive_buffer += chunk.decode("utf-8", errors="replace")
        except (TimeoutError, socket.timeout) as error:
            raise TimeoutError(
                "Timed out waiting for state data from Geometry Dash. "
                "Ensure Level 1 is currently UNPAUSED so game frames are updating!"
            ) from error

        raw_message, self._receive_buffer = self._receive_buffer.split("\n", 1)
        raw_message = raw_message.strip()
        if not raw_message:
            return {}
        return json.loads(raw_message)

    def _normalize_obs(self, payload: dict[str, Any]) -> np.ndarray:
        rays_raw = payload.get("rays", [300.0] * self.NUM_RAYS)

        xPos = float(payload.get("xPos", 0.0))
        yPos = float(payload.get("yPos", 0.0))
        xVel = float(payload.get("xVel", 0.0))
        yVel = float(payload.get("yVel", 0.0))
        rotation = float(payload.get("rotation", 0.0))

        x_norm = (xPos - self._start_x) / 3000.0
        y_norm = (yPos - self.GROUND_Y) / 200.0
        xvel_norm = xVel / self.PLAYER_SPEED_NORM if self.PLAYER_SPEED_NORM != 0 else 0.0
        yvel_norm = np.clip(yVel / self.MAX_Y_VEL, -1.0, 1.0)

        rot_rad = rotation % 360.0
        if rot_rad > 180.0:
            rot_rad -= 360.0
        rot_norm = rot_rad / 180.0

        observation = np.array(
            [
                np.clip(x_norm, -1.0, 1.0),
                np.clip(y_norm, -1.0, 1.0),
                np.clip(xvel_norm, -1.0, 1.0),
                np.clip(yvel_norm, -1.0, 1.0),
                np.clip(rot_norm, -1.0, 1.0),
                1.0 if payload.get("isGrounded", False) else 0.0,
                1.0 if payload.get("isDead", False) else 0.0,
                1.0 if payload.get("hasWon", False) else 0.0,
            ] + [np.clip(float(r) / 300.0, 0.0, 1.0) for r in rays_raw[: self.NUM_RAYS]],
            dtype=np.float32,
        )
        return observation

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        self._send_message({"command": "reset"})
        payload = self._receive_message()
        self._start_x = float(payload.get("xPos", 0.0))
        self._step_count = 0
        self._episode_reward = 0.0
        observation = self._normalize_obs(payload)
        self._last_observation = observation
        return observation, {"bridge_state": payload}

    def step(self, action: int):
        self._send_message({"action": int(action)})
        payload = self._receive_message()
        observation = self._normalize_obs(payload)

        terminated = bool(observation[6] or observation[7])
        is_dead = bool(observation[6])
        is_won = bool(observation[7])
        self._step_count += 1

        reward = 0.0

        reward += 1.0

        if is_dead:
            reward -= 5.0

        if is_won:
            reward += 50.0

        self._episode_reward += reward
        self._last_observation = observation
        return observation, float(reward), terminated, False, {"bridge_state": payload, "raw": payload}

    def close(self) -> None:
        if self._socket is None:
            return

        try:
            self._socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self._socket.close()
        self._socket = None
        self._receive_buffer = ""
