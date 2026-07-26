from __future__ import annotations

import json
import socket
from typing import Iterator


HOST = "127.0.0.1"
PORT = 6969


def iter_lines(connection: socket.socket) -> Iterator[str]:
    buffer = ""
    while True:
        chunk = connection.recv(4096)
        if not chunk:
            return
        buffer += chunk.decode("utf-8", errors="replace")
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            if line:
                yield line


def start_client() -> None:
    print(f"[GatiRL Python] Connecting to the bridge at {HOST}:{PORT}...")
    with socket.create_connection((HOST, PORT), timeout=5.0) as connection:
        connection.settimeout(5.0)
        print("[GatiRL Python] Connected. Sending no-op actions and printing state updates.")
        for line in iter_lines(connection):
            try:
                state = json.loads(line)
            except json.JSONDecodeError:
                continue

            print(
                "Received State -> "
                f"X: {state.get('xPos', 0):.2f}, "
                f"Y: {state.get('yPos', 0):.2f}, "
                f"Y-Vel: {state.get('yVel', 0):.2f}"
            )
            connection.sendall(b'{"action":0}\n')


if __name__ == "__main__":
    start_client()