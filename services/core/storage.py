from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[2]
DB_PATH = Path(__file__).resolve().parent / "data.db"


@dataclass
class ProjectRecord:
    id: str
    name: str
    path: str


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                path TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS permissions (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                allowed_folders TEXT NOT NULL,
                allowed_commands TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )


def ensure_defaults() -> None:
    init_db()
    defaults_path = ROOT_DIR / "config" / "defaults.json"
    defaults = {"allowed_folders": [], "allowed_commands": [], "enabled_skills": []}
    if defaults_path.exists():
        defaults.update(json.loads(defaults_path.read_text(encoding="utf-8")))
    with _connect() as conn:
        cursor = conn.execute("SELECT allowed_folders, allowed_commands FROM permissions WHERE id = 1")
        row = cursor.fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO permissions (id, allowed_folders, allowed_commands) VALUES (1, ?, ?)",
                (
                    json.dumps(defaults.get("allowed_folders", [])),
                    json.dumps(defaults.get("allowed_commands", [])),
                ),
            )
        if get_setting(conn, "enabled_skills") is None:
            set_setting(conn, "enabled_skills", json.dumps(defaults.get("enabled_skills", [])))


def get_setting(conn: sqlite3.Connection, key: str) -> Optional[str]:
    cursor = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    return row["value"] if row else None


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def list_projects() -> List[ProjectRecord]:
    with _connect() as conn:
        rows = conn.execute("SELECT id, name, path FROM projects").fetchall()
        return [ProjectRecord(**dict(row)) for row in rows]


def get_project_by_id(project_id: str) -> Optional[ProjectRecord]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, name, path FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        return ProjectRecord(**dict(row)) if row else None


def add_project(name: str, path: str) -> ProjectRecord:
    with _connect() as conn:
        cursor = conn.execute("SELECT COUNT(*) AS count FROM projects")
        count = cursor.fetchone()["count"]
        project_id = f"project-{count + 1}"
        conn.execute(
            "INSERT INTO projects (id, name, path) VALUES (?, ?, ?)",
            (project_id, name, path),
        )
        return ProjectRecord(id=project_id, name=name, path=path)


def get_permissions() -> Dict[str, List[str]]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT allowed_folders, allowed_commands FROM permissions WHERE id = 1"
        ).fetchone()
        if not row:
            return {"allowed_folders": [], "allowed_commands": []}
        return {
            "allowed_folders": json.loads(row["allowed_folders"]),
            "allowed_commands": json.loads(row["allowed_commands"]),
        }


def update_permissions(allowed_folders: List[str], allowed_commands: List[str]) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE permissions SET allowed_folders = ?, allowed_commands = ? WHERE id = 1",
            (json.dumps(allowed_folders), json.dumps(allowed_commands)),
        )


def add_log(action: str, payload: Dict[str, Any]) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO logs (timestamp, action, payload) VALUES (?, ?, ?)",
            (timestamp, action, json.dumps(payload)),
        )


def list_logs() -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT timestamp, action, payload FROM logs ORDER BY id DESC"
        ).fetchall()
        return [
            {
                "timestamp": row["timestamp"],
                "action": row["action"],
                "payload": json.loads(row["payload"]),
            }
            for row in rows
        ]


def get_enabled_skills() -> List[str]:
    with _connect() as conn:
        value = get_setting(conn, "enabled_skills")
        return json.loads(value) if value else []


def set_enabled_skills(skills: List[str]) -> None:
    with _connect() as conn:
        set_setting(conn, "enabled_skills", json.dumps(skills))
