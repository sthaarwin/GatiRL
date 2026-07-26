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
    """Gymnasium wrapper around the Gati bridge socket protocol."""

    metadata = {"render_modes": []}
    NUM_RAYS = 5

    def __init__(self, host: str = "127.0.0.1", port: int = 6969, timeout_seconds: float = 15.0) -> None:
        super().__init__()
        self.config = BridgeConfig(host=host, port=port, timeout_seconds=timeout_seconds)
        self.action_space = spaces.Discrete(2)
        obs_size = 8 + self.NUM_RAYS  # 8 original + 5 ray distances
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(obs_size,), dtype=np.float32)
        self._socket: Optional[socket.socket] = None
        self._receive_buffer = ""
        self._last_observation = np.zeros(obs_size, dtype=np.float32)

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

    def _state_from_payload(self, payload: dict[str, Any]) -> np.ndarray:
        rays = payload.get("rays", [300.0] * self.NUM_RAYS)
        observation = np.array(
            [
                float(payload.get("xPos", 0.0)),
                float(payload.get("yPos", 0.0)),
                float(payload.get("xVel", 0.0)),
                float(payload.get("yVel", 0.0)),
                float(payload.get("rotation", 0.0)),
                1.0 if payload.get("isGrounded", False) else 0.0,
                1.0 if payload.get("isDead", False) else 0.0,
                1.0 if payload.get("hasWon", False) else 0.0,
            ] + [float(r) for r in rays[: self.NUM_RAYS]],
            dtype=np.float32,
        )
        return observation

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        self._send_message({"command": "reset"})
        payload = self._receive_message()
        observation = self._state_from_payload(payload)
        self._last_observation = observation
        return observation, {"bridge_state": payload}

    def step(self, action: int):
        self._send_message({"action": int(action)})
        payload = self._receive_message()
        observation = self._state_from_payload(payload)

        x_delta = float(observation[0] - self._last_observation[0])
        terminated = bool(observation[6] or observation[7])
        reward = x_delta * 0.1 - (100.0 if observation[6] else 0.0) + (500.0 if observation[7] else 0.0)
        if not terminated:
            reward += 1.0

        self._last_observation = observation
        return observation, float(reward), terminated, False, {"bridge_state": payload}

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
