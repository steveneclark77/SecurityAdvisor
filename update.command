#!/bin/bash
# macOS: double-click in Finder, or run ./update.command in Terminal.
set -Eeuo pipefail

# Finder may supply a smaller PATH than an interactive shell.
export PATH="/usr/local/bin:/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"
step="initializing"
finish() {
    result=$?
    trap - EXIT
    if [ "$result" -ne 0 ]; then
        printf '\nUpdate failed while %s. Review the error above.\n' "$step" >&2
        printf 'No rollback was attempted. If the app was stopped, fix the issue and rerun.\n' >&2
        printf 'For startup failures, inspect: docker compose logs web db\n' >&2
    fi
    if [ "${1:-}" != '--no-pause' ] && [ -t 0 ]; then
        printf '\nPress Return to close...'
        read -r _ || true
    fi
    exit "$result"
}
trap 'finish "${1:-}"' EXIT

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
printf 'Updating SecurityAdvisor. Back up important data before migrations.\n'
printf 'Your .env and database volume will be preserved.\n\n'

step="checking prerequisites"
command -v git >/dev/null
command -v docker >/dev/null
docker info >/dev/null
docker compose version
if [ ! -f .env ]; then
    printf 'Missing .env. Complete initial setup first.\n' >&2
    exit 1
fi
if [ "$(git branch --show-current)" != main ]; then
    printf 'Switch to the main branch before running this updater.\n' >&2
    exit 1
fi
if ! git diff --quiet || ! git diff --cached --quiet; then
    printf 'Commit or save your tracked changes before updating.\n' >&2
    exit 1
fi

step="pulling the latest code"
git pull --ff-only origin main
step="building the application image"
docker compose build web news_scanner
step="starting PostgreSQL"
docker compose up -d --wait db
step="stopping the application for migrations"
docker compose stop web news_scanner
step="applying database migrations"
docker compose run --rm --no-deps web python manage.py migrate --noinput
step="updating unchanged starter guidance"
docker compose run --rm --no-deps web python manage.py seed_library --enrich-existing
step="checking application configuration"
docker compose run --rm --no-deps web python manage.py check
step="restarting the application"
docker compose up -d --force-recreate web news_scanner
step="verifying the login page responds"
docker compose exec -T web python - <<'PY'
import time
import urllib.request

for attempt in range(30):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8000/admin/login/', timeout=3) as response:
            if response.status != 200 or b'csrfmiddlewaretoken' not in response.read():
                raise RuntimeError('Expected login form was not returned.')
        break
    except Exception:
        if attempt == 29:
            raise
        time.sleep(1)
PY
printf '\nSuccess: SecurityAdvisor is updated and responding on local port 8000.\n'
printf 'Existing snapshots and customized guidance were preserved.\n'
