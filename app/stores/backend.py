import json
import sqlite3
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


class SqliteKeyValueStore:
    def __init__(self, path_getter: Callable[[], Path], table_name: str):
        self._path_getter = path_getter
        self._table_name = table_name

    def _connect(self) -> sqlite3.Connection:
        path = self._path_getter()
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self._table_name} (
                record_key TEXT PRIMARY KEY,
                record_value TEXT NOT NULL
            )
            """
        )
        return connection

    def load(self) -> dict[str, dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(f"SELECT record_key, record_value FROM {self._table_name}").fetchall()
        return {key: json.loads(raw_value) for key, raw_value in rows}

    def save(self, records: dict[str, dict[str, object]]) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(f"DELETE FROM {self._table_name}")
                if records:
                    connection.executemany(
                        f"INSERT INTO {self._table_name} (record_key, record_value) VALUES (?, ?)",
                        [(key, json.dumps(value, sort_keys=True)) for key, value in records.items()],
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
