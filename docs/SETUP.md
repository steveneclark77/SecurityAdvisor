# Development setup

## Windows 10

Use WSL2 with Ubuntu and a compatible Docker Desktop version with WSL integration. Check current Windows build/edition requirements and Docker licensing. Windows 10 standard support ended October 14, 2025; use extended security updates or a supported OS before handling sensitive data. Develop with synthetic data for now.

Clone inside WSL's Linux filesystem (such as `~/src/SecurityAdvisor`), rather than `/mnt/c`. VS Code's WSL extension is optional.

## Start locally

Run from the repository root in WSL/Ubuntu:

```bash
cp .env.example .env
```

Generate two different random secrets with a password manager or `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`. Set `DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD` in `.env`. Never commit this file.

```bash
docker compose up --build -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_library
docker compose exec web python manage.py createsuperuser
```

Open the application on your laptop at port 8000 and sign in through the admin login. The port binds only to the local machine. PostgreSQL has no published host port. This is a development server, not a production deployment.

### Review the baseline

1. Browse controls and filter by business profile.
2. Use **Manage controls** to edit working guidance and profile/modifier mappings.
3. Capture a uniquely named snapshot and describe coverage gaps.
4. Review the snapshot, confirm your review, and record approval rationale.
5. Later working edits require a new snapshot; prior snapshots retain their content.

The repeatable seed command creates 20 profiles, eight modifiers, and 14 original draft controls. It preserves existing controls and mappings and never approves anything. Starter guidance is incomplete, not reproduced framework text or validated CIS/sector mappings. Approval records your decision, not certification or completeness.

### Validate and restart

```bash
docker compose exec web python manage.py check
docker compose exec web python manage.py makemigrations --check --dry-run
docker compose exec web python manage.py test
docker compose stop
docker compose start
```

After source changes, rebuild with `docker compose up --build -d`. The database persists in a volume; `docker compose down -v` deletes it. A volume is not a backup.

## Python-only fallback

Python 3.12 is the container runtime. SQLite is an explicit development/test fallback, not a substitute for PostgreSQL concurrency validation.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export DATABASE_ENGINE=sqlite
export DJANGO_DEBUG=true
python manage.py migrate
python manage.py seed_library
python manage.py createsuperuser
python manage.py test
python manage.py runserver 127.0.0.1:8000
```

Outside Compose, settings do not load `.env` automatically. PostgreSQL is the default backend; configure `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` to use it directly. `DJANGO_SECRET_KEY` is mandatory. Debug defaults off; examples enable it for local HTTP.

## Builds behind a trusted TLS inspection proxy

The Dockerfile accepts an optional BuildKit secret named `pip_ca_bundle` containing your organization's approved PEM CA bundle. Supply it through a local Compose override or `docker build --secret id=pip_ca_bundle,src=/path/to/approved-ca-bundle.pem .`. The bundle is used for verified package downloads during build and is not copied into the image. Ordinary builds need no override. Never disable TLS verification to work around a trust failure.

## Production boundary and retention

Customer intake, customer records, uploads, MFA, news ingestion, and retention automation are not implemented yet. Do not store sensitive customer data in this milestone. Production requires reviewed authentication/MFA, HTTPS, a production server and static-file serving, customer authorization, encrypted storage/backups, restore testing, and retention/deletion controls.

Retention is three years. Engagement closure is a proposed starting point, not yet approved. Attachment, history, backup, and exception treatment remains to be defined. Operations are expected to be US-only with no additional data-location requirement.

The UI uses Django templates and local CSS without external browser dependencies. HTMX/Bootstrap remain options when needed. Scheduled management commands can support future daily ingestion; no scheduler or AI service is required now.

## Upgrade an existing library to detailed actions

After fetching this revision and rebuilding the web container, run:

```bash
docker compose up --build -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_library --enrich-existing
```

The migration adds ordered action records. The enrichment command explicitly updates unchanged original starter guidance; customized controls without actions are listed and preserved for manual review. Existing action lists are never overwritten. Ordinary `seed_library` only adds new starter records. No command rewrites snapshots or approves a baseline.

Each action has a stable database identity, order, instruction, applicability/exceptions, verification, and optional references. Edit them through the control's admin page. Customer-specific completion tracking will be added with assessments; library actions themselves are not completion checkboxes. References on the control apply to its actions; optional action references can link vendor instructions without making shared guidance vendor-dependent. Capture a new baseline after reviewing enriched guidance.

## One-command updates on macOS

After the initial installation, run `git pull origin main` once to obtain the updater. Start Docker Desktop, then double-click **update.command** in Finder, or run from the repository folder in Terminal:

```bash
./update.command
```

Git preserves its executable permission. If necessary after a manual download, run `chmod +x update.command`. If macOS blocks opening a downloaded script, review it before using Finder's Open option or executing it from Terminal; do not disable system security protections.

The updater requires Git, Docker Desktop with Compose, an existing `.env`, and a clean `main` branch. It runs from its own folder, fast-forwards from GitHub, builds the web image, starts PostgreSQL, stops the web app, applies migrations and safe starter-guidance enrichment, checks configuration, restarts the app, and verifies the login page responds.

It stops on errors and retains `.env`, the database volume, customized guidance, and historical baseline snapshots. Back up important data before migrations: it does not create backups or roll back updates. If a failure occurs after the web app stops, correct the reported issue and rerun. Inspect `docker compose logs web db` for startup problems.

For unattended execution, use `./update.command --no-pause`. Otherwise, interactive runs wait for Return before closing so results remain visible. Failures return a nonzero exit code. This script also runs in Bash on Linux/WSL; it is not a Windows batch file.
