# Local Smart Assistant Build Plan

## Goal
Build a local desktop app you can manage with:

- Skills on/off
- Allowed folders + allowed commands
- Projects
- Memory (opt-in)
- Audit logs
- Ability to code, apply patches, and run tests in your repos

Recommended architecture: **Desktop UI (Tauri)** + **Local backend (FastAPI)** + **Codex as the coding agent**.

Codex runs locally in your repo and can read/edit/run code in that directory via terminal.

---

## Architecture Overview

### 1) Desktop App UI (Tauri)
**Tabs:**
- Chat
- Projects
- Skills
- Permissions
- Logs
- Settings

**Responsibilities:**
- Provide the control surface for configuration and approvals.
- Show task progress, diffs, and test results.
- Surface audit logs and a searchable history of actions.

### 2) Local Core Service (FastAPI)
**Endpoints:**
- `POST /chat` — chat + routing
- `POST /codex/run` — launch Codex task for a project
- `GET /projects` / `POST /projects`
- `GET /logs` — audit trail
- `POST /permissions` — allowlist folders/commands

**Responsibilities:**
- Enforce permissions, approvals, and logging.
- Run Codex in project scope and collect results.
- Persist project config and skill status.

### 3) Skills System
Each skill is a folder with:
- `manifest.json` (name, tools, permissions)
- `prompt.md` (guidance)
- Optional `validators.py` (rules)

**Starter skills (high value):**
- `code_repair` (diff-first)
- `test_runner` (npm/pytest allowlist)
- `project_profiler` (stores lint/test commands, conventions)
- `safe_terminal` (runs only approved commands)
- `doc_builder` (README/specs)
- `sage_layer` (kind + wise tone + truthfulness checks)

### 4) Permission Model (Non‑negotiable)
- Allowlisted folders only (read/write)
- Allowlisted commands only
- “Approve to apply patch” and “Approve to run command”
- Log everything (what, when, result)

---

## Build Phases

### Phase 1 — App shell + configuration
- Create Tauri UI with tabs + settings screens.
- Add config store for:
  - Projects list
  - Allowed folders
  - Allowed commands
  - Enabled skills

### Phase 2 — Coding loop (diff → approve → test)
- Implement “propose patch” screen.
- Add terminal runner with allowlist enforcement.
- Add test runner.
- Add logs screen.

### Phase 3 — Integrate Codex
- Use Codex CLI to do code tasks inside a repo.
- Capture outputs, patches, and test results back into your UI.

### Phase 4 — Wisdom layer
- Always‑on “kind + wise” style rules.
- “Truthfulness” checks (state assumptions; verify when possible).
- “Safety boundaries” (no risky automation without approval).

---

## Codex (CLI-first) Workflow

### 1) Install Codex CLI
```bash
npm i -g @openai/codex
```
(Alternative on macOS: Homebrew cask is supported.)

### 2) Run Codex in a project (interactive)
```bash
cd path/to/your/repo
codex
```
Or start with a prompt:
```bash
codex "Explain this codebase to me"
```

### 3) First‑time authentication
- First run prompts for sign‑in (ChatGPT account) or API key.

### 4) Configure Codex settings
- Global config: `~/.codex/config.toml`
- Project config: `.codex/config.toml` in repo

Use these to align with your assistant rules (diff‑first, approvals, preferred commands).

### 5) Tight loop workflow (repro → fix → verify)
Provide:
- The bug
- Exact repro steps
- Suspected files
- Expected behavior

---

## Codex Integration Options

### Option A (simplest): Call Codex CLI from backend
- FastAPI runs `codex` in the project directory.
- Capture stdout/stderr.
- Show results in UI.
- Best for “Run Codex on this project” button.

### Option B (more control): Codex SDK (TypeScript)
Install:
```bash
npm install @openai/codex-sdk
```
Use SDK when you want:
- Richer session control
- Structured results
- Embedded Codex logic in app backend

---

## Windows Note
Windows support is experimental; for best results use WSL workspace and follow Windows setup guidance.
