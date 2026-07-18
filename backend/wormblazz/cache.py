from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from .models import SocialNetwork


class NetworkCache:
    """Thread-safe JSON cache that survives application restarts."""

    def __init__(self, cache_dir: str | Path | None = None) -> None:
        configured = cache_dir or os.getenv("WORMBLAZZ_CACHE_DIR", ".cache")
        self.directory = Path(configured)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._memory: dict[str, SocialNetwork] = {}
        self._lock = threading.RLock()

    def get(self, network_id: str) -> SocialNetwork | None:
        with self._lock:
            if network_id in self._memory:
                return self._memory[network_id]

            path = self._path(network_id)
            if not path.exists():
                return None

            try:
                network = SocialNetwork.model_validate_json(path.read_text())
            except (OSError, ValueError):
                return None

            self._memory[network_id] = network
            return network

    def set(self, network: SocialNetwork) -> None:
        with self._lock:
            self._memory[network.network_id] = network
            destination = self._path(network.network_id)
            temporary = destination.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(network.model_dump(mode="json"), ensure_ascii=False, indent=2)
            )
            temporary.replace(destination)

    def _path(self, network_id: str) -> Path:
        safe_id = "".join(
            character if character.isalnum() or character in "-_." else "_"
            for character in network_id
        )
        return self.directory / f"{safe_id}.json"

