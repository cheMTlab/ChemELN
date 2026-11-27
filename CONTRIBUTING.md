# Contributing to CheMTlab

Thanks for helping build an open lab notebook for everyone.

## Ground rules
- Be kind. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
- Report security problems privately. See [SECURITY.md](SECURITY.md).
- By contributing, you agree that your contributions are licensed under AGPL-3.0-or-later.

## Development setup
1. Install Docker, Node 22 and [uv](https://docs.astral.sh/uv/).
2. `cp .env.example .env`
3. `docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build`
4. Install the git hooks: `uvx pre-commit install`

### Backend only (without Docker)
```bash
cd backend
uv sync
# A PostgreSQL with the RDKit cartridge is needed for chemistry features.
# For non-chemistry work you can use SQLite:
DATABASE_URL=sqlite:///dev.sqlite3 uv run python manage.py migrate
DATABASE_URL=sqlite:///dev.sqlite3 uv run pytest
```

### Frontend only
```bash
cd frontend
npm install
npm run dev      # proxies /api to http://localhost:8000
npm test
```

## Pull requests
- Keep PRs focused, and add tests for new behaviour.
- Run `uvx pre-commit run --all-files` before pushing.
- Database changes need a migration (`python manage.py makemigrations`).
- For any feature that sends data off the server (external lookups, AI), make it **opt-in** and off by default.
