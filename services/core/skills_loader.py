from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT_DIR = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT_DIR / "skills"


def load_skills() -> List[Dict[str, Any]]:
    skills: List[Dict[str, Any]] = []
    if not SKILLS_DIR.exists():
        return skills
    for manifest_path in sorted(SKILLS_DIR.glob("*/manifest.json")):
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        data["prompt_path"] = manifest_path.parent / "prompt.md"
        skills.append(data)
    return skills


def read_skill_prompt(skill_name: str) -> Optional[str]:
    for manifest in load_skills():
        if manifest["name"] == skill_name:
            prompt_path = Path(manifest["prompt_path"])
            if prompt_path.exists():
                return prompt_path.read_text(encoding="utf-8")
            return None
    return None
