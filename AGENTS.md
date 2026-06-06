# Repository Guide for Agents

## Repository Overview

This repository is named `calendar_matching`. Its current purpose is described in Dutch in `README.md` as:

> App om 2 kalenders met elkaar te vergelijken en uit te testen.

In English: this is intended to be an app for comparing two calendars and testing them.

## Current Contents

At the time this guide was written, the repository contains only a minimal project skeleton:

- `README.md` — project title and short Dutch description.
- `.gitignore` — Python-focused ignore rules for bytecode, virtual environments, build outputs, test caches, coverage reports, local environment files, and common editor/tool caches.
- `AGENTS.md` — this guide.

No application source files, dependency manifests, test suites, or build scripts are present yet.

## Development Notes

- Treat this as an early-stage Python-oriented project unless future files indicate otherwise.
- Keep generated artifacts, virtual environments, local environment files, caches, build outputs, and coverage output out of version control, following `.gitignore`.
- If adding Python code, prefer a clear project structure and include any needed dependency and test configuration files.
- Update `README.md` when adding runnable functionality so future contributors know how to install, run, and test the project.

## Testing

There is currently no automated test command configured. When adding behavior, also add tests and document the test command in `README.md`.
