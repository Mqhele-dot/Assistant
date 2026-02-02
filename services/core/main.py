from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from skills_loader import load_skills, read_skill_prompt
from storage import (
    add_log,
    add_project,
    ensure_defaults,
    get_enabled_skills,
    get_permissions,
    get_project_by_id,
    list_logs as fetch_logs,
    list_projects as fetch_projects,
    set_enabled_skills,
    update_permissions as persist_permissions,
)

app = FastAPI(title="Local Smart Assistant Core")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:1420",
        "http://127.0.0.1",
        "http://127.0.0.1:1420",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SKILLS = load_skills()

ensure_defaults()

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    project_id: Optional[str] = None


class ChatResponse(BaseModel):
    message: str
    route: str


class CodexRunRequest(BaseModel):
    project_id: str
    prompt: str = Field(..., min_length=1)


class CodexRunResponse(BaseModel):
    status: str
    detail: str
    output: Optional[str] = None


class Project(BaseModel):
    id: str
    name: str
    path: str


class ProjectCreateRequest(BaseModel):
    name: str
    path: str


class PermissionsRequest(BaseModel):
    allowed_folders: List[str] = Field(default_factory=list)
    allowed_commands: List[str] = Field(default_factory=list)


class AuditLog(BaseModel):
    timestamp: str
    action: str
    payload: Dict[str, Any]


class SkillSummary(BaseModel):
    name: str
    description: str
    tools: List[str]
    permissions: List[str]
    enabled: bool


class SkillToggleRequest(BaseModel):
    name: str
    enabled: bool


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


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    enabled_skills = set(get_enabled_skills())
    route = "assistant"
    if request.project_id:
        route = "code_repair" if "code_repair" in enabled_skills else "codex"
    add_log(
        "chat",
        {
            **request.model_dump(),
            "applied_skills": sorted(enabled_skills.intersection({"sage_layer"})),
        },
    )
    return ChatResponse(message="Received message.", route=route)


@app.post("/codex/run", response_model=CodexRunResponse)
async def codex_run(request: CodexRunRequest) -> CodexRunResponse:
    permissions = get_permissions()
    enabled_skills = set(get_enabled_skills())
    project = get_project_by_id(request.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    if not _is_path_allowed(project.path, permissions["allowed_folders"]):
        add_log("codex_denied", {"reason": "path_not_allowed", "project": project.id})
        raise HTTPException(status_code=403, detail="Project path is not allowed.")
    if "safe_terminal" not in enabled_skills:
        add_log("codex_denied", {"reason": "safe_terminal_disabled", "project": project.id})
        raise HTTPException(status_code=403, detail="safe_terminal skill is required.")
    if not _is_command_allowed("codex", permissions["allowed_commands"]):
        add_log("codex_denied", {"reason": "command_not_allowed", "command": "codex"})
        raise HTTPException(status_code=403, detail="Codex command not allowlisted.")

    add_log("codex_run", request.model_dump())
    import subprocess

    result = subprocess.run(
        ["codex", request.prompt],
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
    return CodexRunResponse(
        status=status,
        detail=f"Codex run completed for project {project.id}.",
        output=output,
    )


@app.get("/projects", response_model=List[Project])
async def list_projects() -> List[Project]:
    add_log("projects_list", {})
    return [Project(id=proj.id, name=proj.name, path=proj.path) for proj in fetch_projects()]


@app.post("/projects", response_model=Project)
async def create_project(request: ProjectCreateRequest) -> Project:
    permissions = get_permissions()
    if not _is_path_allowed(request.path, permissions["allowed_folders"]):
        add_log("projects_denied", {"reason": "path_not_allowed", "path": request.path})
        raise HTTPException(status_code=403, detail="Project path is not allowed.")
    project = add_project(request.name, request.path)
    add_log("projects_create", {"id": project.id, "name": project.name, "path": project.path})
    return Project(id=project.id, name=project.name, path=project.path)


@app.get("/logs", response_model=List[AuditLog])
async def list_logs() -> List[AuditLog]:
    return [AuditLog(**log) for log in fetch_logs()]


@app.post("/permissions")
async def update_permissions(request: PermissionsRequest) -> Dict[str, List[str]]:
    persist_permissions(request.allowed_folders, request.allowed_commands)
    add_log("permissions_update", request.model_dump())
    return get_permissions()


@app.get("/skills", response_model=List[SkillSummary])
async def list_skills() -> List[SkillSummary]:
    enabled = set(get_enabled_skills())
    return [
        SkillSummary(
            name=skill["name"],
            description=skill["description"],
            tools=skill["tools"],
            permissions=skill["permissions"],
            enabled=skill["name"] in enabled,
        )
        for skill in SKILLS
    ]


@app.post("/skills/enable")
async def enable_skill(request: SkillToggleRequest) -> Dict[str, List[str]]:
    enabled = set(get_enabled_skills())
    if request.enabled:
        enabled.add(request.name)
    else:
        enabled.discard(request.name)
    set_enabled_skills(sorted(enabled))
    add_log("skill_toggle", request.model_dump())
    return {"enabled_skills": sorted(enabled)}


@app.get("/skills/{skill_name}/prompt")
async def get_skill_prompt(skill_name: str) -> Dict[str, str]:
    prompt = read_skill_prompt(skill_name)
    if prompt is None:
        raise HTTPException(status_code=404, detail="Skill not found.")
    return {"name": skill_name, "prompt": prompt}


@app.get("/health")
async def health() -> Dict[str, bool]:
    return {"ok": True}
