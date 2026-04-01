import json
from collections.abc import Callable
from pathlib import Path
from typing import Protocol


class KeyValueStore(Protocol):
    def load(self) -> dict[str, dict[str, object]]:
        ...

    def save(self, records: dict[str, dict[str, object]]) -> None:
        ...


class JsonFileKeyValueStore:
    def __init__(self, path_getter: Callable[[], Path]):
        self._path_getter = path_getter

    def load(self) -> dict[str, dict[str, object]]:
        path = self._path_getter()
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def save(self, records: dict[str, dict[str, object]]) -> None:
        path = self._path_getter()
        path.write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")
