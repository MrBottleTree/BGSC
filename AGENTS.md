# Repository Guidelines

## Project Structure & Module Organization
- Code: `bgsc/` (project config) and `games/` (Django app).
- Entrypoint: `manage.py` for all admin/dev commands.
- URLs & settings: `bgsc/urls.py`, `bgsc/settings.py`.
- App modules: `games/models.py`, `games/views.py`, `games/urls.py`, `games/admin.py`.
- Migrations: `games/migrations/` (auto‑generated). Tests: `games/tests.py`.
- Local DB (dev only): `db.sqlite3`.

## Build, Test, and Development Commands
- Create venv: `python -m venv .venv && .\.venv\Scripts\activate` (Windows).
- Install deps: `pip install django` or `pip install -r requirements.txt` (if present).
- Run server: `python manage.py runserver` (serves at `http://127.0.0.1:8000`).
- Make migrations: `python manage.py makemigrations games`.
- Apply migrations: `python manage.py migrate`.
- Run tests: `python manage.py test`.

## Coding Style & Naming Conventions
- Python style: PEP 8, 4‑space indentation, 100‑120 col soft limit.
- Naming: `snake_case` functions/vars, `PascalCase` models/classes, `lowercase_with_underscores.py` files.
- Imports: standard lib → third‑party → local. Prefer explicit relative imports inside apps.
- Optional tools: `black` and `isort` (use if configured in your environment).

## Testing Guidelines
- Framework: Django test runner with `unittest` in `games/tests.py`.
- Write unit tests for models (managers/validators) and views (status codes, templates, permissions).
- Name tests clearly (e.g., `test_view_shows_fixture_list`).
- Run locally with an isolated test DB: `python manage.py test`.

## Commit & Pull Request Guidelines
- Commits: small, focused, imperative mood (e.g., "Add league standings view").
- Message body: what/why, notable tradeoffs, migration impacts.
- Branches: `feature/short-description`, `fix/issue-123`.
- PRs: include description, linked issues, before/after notes, and screenshots for UI changes.
- Ensure migrations are included when models change; do not commit local `db.sqlite3`.

## Security & Configuration Tips
- Do not hardcode secrets. Prefer env vars for `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`.
- Use local `.env` (untracked) and mirror keys in `bgsc/settings.py` lookup.
- Keep `DEBUG` off in production and run `collectstatic` if static files are added later.

