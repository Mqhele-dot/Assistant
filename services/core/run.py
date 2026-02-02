from __future__ import annotations

import json
import subprocess
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from skills_loader import load_skills, read_skill_prompt
from storage import (
    add_log,
    add_project,
    ensure_defaults,
    get_enabled_skills,
    get_permissions,
    get_project_by_id,
    list_logs,
    list_projects,
    set_enabled_skills,
    update_permissions,
)


def _json_response(handler: BaseHTTPRequestHandler, payload: Any, status: int = 200) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> Dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    if length == 0:
        return {}
    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8"))


def _is_path_allowed(path: str, allowed_folders: List[str]) -> bool:
    if not allowed_folders:
        return False
    target = Path(path).expanduser().resolve()
    for folder in allowed_folders:
        try:
            allowed = Path(folder).expanduser().resolve()
        except FileNotFoundError:
            continue
        if allowed in target.parents or allowed == target:
            return True
    return False


def _is_command_allowed(command: str, allowlist: List[str]) -> bool:
    return any(command == allowed or command.startswith(f"{allowed} ") for allowed in allowlist)


class CoreHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib signature
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            _json_response(self, {"ok": True})
            return
        if parsed.path == "/projects":
            add_log("projects_list", {})
            projects = [
                {"id": proj.id, "name": proj.name, "path": proj.path}
                for proj in list_projects()
            ]
            _json_response(self, projects)
            return
        if parsed.path == "/logs":
            _json_response(self, list_logs())
            return
        if parsed.path == "/skills":
            enabled = set(get_enabled_skills())
            skills = [
                {
                    "name": skill["name"],
                    "description": skill["description"],
                    "tools": skill["tools"],
                    "permissions": skill["permissions"],
                    "enabled": skill["name"] in enabled,
                }
                for skill in load_skills()
            ]
            _json_response(self, skills)
            return
        if parsed.path.startswith("/skills/") and parsed.path.endswith("/prompt"):
            skill_name = parsed.path.split("/")[2]
            prompt = read_skill_prompt(skill_name)
            if prompt is None:
                _json_response(self, {"detail": "Skill not found."}, status=404)
                return
            _json_response(self, {"name": skill_name, "prompt": prompt})
            return
        _json_response(self, {"detail": "Not Found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802 - stdlib signature
        parsed = urlparse(self.path)
        payload = _read_json(self)
        if parsed.path == "/chat":
            enabled = set(get_enabled_skills())
            route = "assistant"
            if payload.get("project_id"):
                route = "code_repair" if "code_repair" in enabled else "codex"
            add_log(
                "chat",
                {
                    **payload,
                    "applied_skills": sorted(enabled.intersection({"sage_layer"})),
                },
            )
            _json_response(self, {"message": "Received message.", "route": route})
            return
        if parsed.path == "/projects":
            permissions = get_permissions()
            if not _is_path_allowed(payload.get("path", ""), permissions["allowed_folders"]):
                add_log("projects_denied", {"reason": "path_not_allowed", "path": payload.get("path")})
                _json_response(self, {"detail": "Project path is not allowed."}, status=403)
                return
            project = add_project(payload.get("name", ""), payload.get("path", ""))
            add_log("projects_create", {"id": project.id, "name": project.name, "path": project.path})
            _json_response(self, {"id": project.id, "name": project.name, "path": project.path})
            return
        if parsed.path == "/permissions":
            update_permissions(
                payload.get("allowed_folders", []),
                payload.get("allowed_commands", []),
            )
            add_log("permissions_update", payload)
            _json_response(self, get_permissions())
            return
        if parsed.path == "/skills/enable":
            enabled = set(get_enabled_skills())
            if payload.get("enabled"):
                enabled.add(payload.get("name"))
            else:
                enabled.discard(payload.get("name"))
            set_enabled_skills(sorted(enabled))
            add_log("skill_toggle", payload)
            _json_response(self, {"enabled_skills": sorted(enabled)})
            return
        if parsed.path == "/codex/run":
            permissions = get_permissions()
            enabled_skills = set(get_enabled_skills())
            project = get_project_by_id(payload.get("project_id", ""))
            if project is None:
                _json_response(self, {"detail": "Project not found."}, status=404)
                return
            if not _is_path_allowed(project.path, permissions["allowed_folders"]):
                add_log("codex_denied", {"reason": "path_not_allowed", "project": project.id})
                _json_response(self, {"detail": "Project path is not allowed."}, status=403)
                return
            if "safe_terminal" not in enabled_skills:
                add_log("codex_denied", {"reason": "safe_terminal_disabled", "project": project.id})
                _json_response(self, {"detail": "safe_terminal skill is required."}, status=403)
                return
            if not _is_command_allowed("codex", permissions["allowed_commands"]):
                add_log("codex_denied", {"reason": "command_not_allowed", "command": "codex"})
                _json_response(self, {"detail": "Codex command not allowlisted."}, status=403)
                return
            add_log("codex_run", payload)
            result = subprocess.run(
                ["codex", payload.get("prompt", "")],
                cwd=project.path,
                capture_output=True,
                text=True,
            )
            output = (result.stdout or "") + (result.stderr or "")
            add_log(
                "codex_result",
                {
                    "project_id": project.id,
                    "returncode": result.returncode,
                    "output": output,
                },
            )
            status = "success" if result.returncode == 0 else "failed"
            _json_response(
                self,
                {
                    "status": status,
                    "detail": f"Codex run completed for project {project.id}.",
                    "output": output,
                },
            )
            return
        _json_response(self, {"detail": "Not Found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003 - stdlib
        return


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    ensure_defaults()
    server = HTTPServer((host, port), CoreHandler)
    server.serve_forever()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the core service without FastAPI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    run(args.host, args.port)
