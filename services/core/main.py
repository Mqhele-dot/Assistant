from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Local Smart Assistant Core")


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


projects: Dict[str, Project] = {}
permissions: Dict[str, List[str]] = {
    "allowed_folders": [],
    "allowed_commands": [],
}
logs: List[AuditLog] = []


def _log(action: str, payload: Dict[str, Any]) -> None:
    logs.append(
        AuditLog(
            timestamp=datetime.now(timezone.utc).isoformat(),
            action=action,
            payload=payload,
        )
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    _log("chat", request.model_dump())
    route = "codex" if request.project_id else "assistant"
    return ChatResponse(message="Received message.", route=route)


@app.post("/codex/run", response_model=CodexRunResponse)
async def codex_run(request: CodexRunRequest) -> CodexRunResponse:
    _log("codex_run", request.model_dump())
    return CodexRunResponse(
        status="queued",
        detail=f"Codex task queued for project {request.project_id}.",
    )


@app.get("/projects", response_model=List[Project])
async def list_projects() -> List[Project]:
    _log("projects_list", {})
    return list(projects.values())


@app.post("/projects", response_model=Project)
async def create_project(request: ProjectCreateRequest) -> Project:
    project_id = f"project-{len(projects) + 1}"
    project = Project(id=project_id, name=request.name, path=request.path)
    projects[project_id] = project
    _log("projects_create", project.model_dump())
    return project


@app.get("/logs", response_model=List[AuditLog])
async def list_logs() -> List[AuditLog]:
    return logs


@app.post("/permissions")
async def update_permissions(request: PermissionsRequest) -> Dict[str, List[str]]:
    permissions["allowed_folders"] = request.allowed_folders
    permissions["allowed_commands"] = request.allowed_commands
    _log("permissions_update", request.model_dump())
    return permissions
