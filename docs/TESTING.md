# Application and browser regression checks

All fixtures are synthetic. Django creates and destroys a dedicated test database; no test command starts an engagement against a real company. Browser uploads use temporary private storage.

## Server-side suite

Run `python manage.py test` in the configured development environment, or `docker compose exec web python manage.py test`.

The CSRF matrix enables Django's real CSRF enforcement for every application POST route. For 44 form operations, including intake draft/final submission and evidence response, it verifies:

- The rendered form contains a token and uses the same-origin referrer policy.
- Missing/incorrect tokens, foreign origins, and null origins return HTTP 403.
- Valid HTTP Origin submissions and HTTPS Referer fallback submissions succeed and persist the expected result.
- New mutating application routes must be added to the operation inventory; the coverage test fails otherwise.

This complements authorization and workflow tests; it does not substitute CSRF tests for customer-access checks. Built-in admin forms are covered by representative real-browser tests, rather than enumerating every Django-provided user/group administration screen.

## Real browsers

Use a Python 3.12 development virtual environment. Browser tooling is separate from production requirements:

```bash
pip install -r requirements-browser.txt
python -m playwright install chromium webkit
export DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export DJANGO_DEBUG=true
export DATABASE_ENGINE=sqlite
E2E_BROWSER=chromium python manage.py test e2e.browser_suite --verbosity 2
E2E_BROWSER=webkit python manage.py test e2e.browser_suite --verbosity 2
```

On Linux, use `python -m playwright install --with-deps chromium webkit` if required system libraries are missing. On macOS, use the supported OS/browser prerequisites from Playwright's installation guidance. WebKit exercises Safari's browser engine but does not replace testing a specific shipped Safari version on a Mac.

The browser suite is explicitly named `browser_suite.py` so ordinary test discovery does not silently skip tests or require Playwright. CI runs it explicitly for both engines. Missing browsers/dependencies fail their job; they do not count as passing or skipped validation.

Coverage includes:

- Real login, logout, and password changes (including CSRF token rotation).
- Intake Save progress, reload, final submission, persistence, and single-use enforcement.
- Public multipart evidence upload and protection against invitation referrer leakage to another origin.
- Every authenticated application form operation: baseline creation/approval/revision/supersession; customers, engagements, assessments, action results, evidence requests/uploads, findings, remediation/retesting, contacts/links, invitations/revocation, reports, reassessment decisions, and inventory items/connections/information follow-ups.
- Representative admin control/inline-action saves and profile/modifier creation.

Tests interact with rendered forms, their scripts, cookies, browser-generated Origin headers, and actual navigation. The browser server uses local HTTP; HTTPS Origin/Referer enforcement is exercised separately by the server-side matrix. A stale pre-login form must be rejected after login rotates its token, and reloading must recover normal saving. They do not inject CSRF tokens or force a successful Origin header. ORM outcome checks run on a separate synchronous thread, retaining Django's async-safety guard.

`test-artifacts/` contains synthetic traces/screenshots and is ignored by Git and Docker. View a trace locally using `python -m playwright show-trace test-artifacts/chromium/<test-name>.zip`. Do not run these tests against production or include real customer information in fixtures or artifacts.

For an environment with a preinstalled browser, `E2E_EXECUTABLE_PATH` can explicitly select its executable. CI uses Playwright-managed browsers. `PLAYWRIGHT_BROWSERS_PATH` can place downloads in a writable directory.

## GitHub Actions

`Application tests` runs on PRs, pushes to main, and manual requests:

- Django tests and migration checks against PostgreSQL 17.
- Browser forms (chromium).
- Browser forms (webkit).

The existing Ruff workflow remains separate. Once these jobs have run successfully on GitHub, select their actual check names in the main-branch ruleset if you want them required. Creating the workflow does not change repository protection settings. Artifact retention is seven days; traces contain only synthetic test credentials and data.

## News ingestion

`python manage.py test news` covers synthetic RSS/Atom ingestion, deduplication, baseline gating, disabled sources, invalid/entity XML, network restrictions, failure retention, permissions, and review validation. The browser suite also verifies source creation with disabled incomplete-input buttons, issue triage, and retained manual review snapshots. No live publisher request is part of these tests. See [NEWS.md](NEWS.md) for the separate live endpoint check.

Version-history coverage additionally checks stale edits, reference-only/source changes, exact-version reviews, model/queryset/raw-SQL immutability, quota rollback, publisher proposals, and an isolated legacy-data migration including refused downgrade. A PostgreSQL-only concurrent-edit test exercises row locks (explicitly skipped on SQLite). The browser news test creates a successor with a source reference before reviewing that exact version. SQLite live-server test teardown temporarily removes history triggers only while destroying its synthetic database contents; application requests always run with the guards installed.

Source identity tests cover the actual URL primary key, normalized duplicate rejection, preventing new-instance overwrites, permanent website identity, repeatable seeding without overwriting configuration, and legacy source audit history. Migration tests run in temporary SQLite/PostgreSQL databases on the selected backend, including populated numeric-to-URL foreign-key conversion and a duplicate-URL failure that must preserve rows and immutability guards. PostgreSQL test credentials need the same database creation/deletion privileges required by Django's normal test runner.

Automatic-scan configuration tests verify that a disabled worker performs no database queries or feed requests, enabled loop mode retains baseline and source restrictions, and manual scans work with automatic scanning disabled.
