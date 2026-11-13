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

Customer workflow features support synthetic exercises only. MFA and retention automation remain unimplemented. News collection requires configured feeds and manual review. Do not store sensitive customer data yet. Production requires reviewed authentication/MFA, HTTPS, a production server and static-file serving, authorization review, encrypted storage/backups, malware scanning, restore testing, and retention/deletion controls.

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

## Customer workflow milestone

After applying migrations, select **Customer engagements**. Follow [the synthetic engagement walkthrough](ENGAGEMENT_WALKTHROUGH.md). Updates do not create customers or approve baselines automatically.

Private evidence attachments persist in a separate `evidence_data` Docker volume and are downloadable only through assigned-customer authorization. Include both the PostgreSQL database and evidence volume in any future backup/migration plan. A volume is not a backup. Do not use `docker compose down -v` unless you intend to remove both.

The new workflow supports synthetic customer/engagement records, scoped intake/evidence links, pinned assessments, action observations, evidence, findings, remediation, retests, preserved printable reports, history, and affected-customer reviews. Account MFA, production encryption and recovery operations, malware scanning, retention automation, and a team-assignment management UI remain outstanding. Keep all exercises synthetic. No notification or email is sent by issuing a link or scheduling a review.


## Revise an unapproved baseline

Open the draft snapshot and choose **Revise this draft**. Follow the page's links to edit controls/actions or profile/modifier mappings in the shared working library, save them, and return to the revision page. Enter a unique replacement version, updated coverage gaps, and the reason for revision. **Create replacement and supersede old draft** captures current working content and marks the original **Superseded** in one transaction. The replacement still requires explicit review and approval.

If a newer replacement snapshot already exists, use **Already captured a replacement?** on the same page instead. Both versions retain their captured contents, and the original records the replacement link, actor, timestamp, and reason. A superseded draft cannot be approved or revised again; follow its replacement link. Approved baselines remain immutable and cannot be superseded through this draft-only workflow.

Revision does not restore the original snapshot into the working library. The replacement includes all currently saved working changes, including unrelated edits made since the original capture. Failed creation leaves the original awaiting review. Existing snapshots receive no automatic status change during migration.


## Contact workflow (v0.1.3)

Updates preserve the original free-text contact in a legacy note. After creating an engagement, add contacts on the second screen, then continue. Existing engagements use **Manage contacts**. New assessments require an active contact; existing assessments and historical owner/authorization text are unchanged. A contact directory supports independent records and explicit-permission reuse. Shared edits prompt for confirmation; archive or deactivate links to preserve history. Roles do not grant login access or authorize work.


## Intake Save progress CSRF fix (v0.1.6)

Earlier intake/evidence pages used a `no-referrer` meta policy that caused browser form POSTs to send `Origin: null`, which Django correctly rejected. The policy is now `same-origin`, preserving same-origin submission while withholding referrers from other origins. CSRF middleware and token validation remain enabled; null and foreign origins remain rejected.

After updating/rebuilding, reload the intake page from its original invitation URL before submitting. If a previous save returned 403, it was not persisted; copy any recoverable text from your browser before reloading. Previously saved drafts remain intact. Do not add `null` to trusted origins or exempt these forms from CSRF protection.


## Inventory workflow (v0.1.8)

Run the normal updater to apply additive inventory/assessment migrations. Existing intakes, approvals, findings, and reports are preserved; old assessments are not backfilled with current inventory facts. Use the Inventory header entry or engagement shortcut and follow [INVENTORY.md](INVENTORY.md). This inventory captures facts and dependencies; it does not scan systems or certify safeguards automatically.

## News collection (v0.1.9)

The normal updater applies additive News migrations and starts the daily `news_scanner` worker. Manage publisher feeds and candidates in Django admin; see [NEWS.md](NEWS.md) for permissions, feed validation, pause/retry behavior, and network requirements. The worker waits for an approved baseline and never changes customer records or approved guidance.

## Issue version history (v0.1.10)

The normal updater migrates existing news issues into immutable version 1 records, preserving old review snapshots without guessing exact version links. It stops both application and scanner during migration. Back up first: these history migrations refuse downgrade; restoring a pre-upgrade backup is the supported rollback. See [NEWS.md](NEWS.md) for next-version editing, per-version sources, network requirements, and configurable ingestion quotas.

## URL-based source identity (v0.1.11)

News sources use their canonical website URL as the database primary key. The updater transfers issue, scan, and version-reference relationships while retaining old numeric IDs and historical snapshots. It also seeds CISA, UpGuard, Schneier on Security, and SecurityWeek without overwriting existing URL-matched configuration. Existing duplicate canonical websites stop migration for review rather than being merged silently. Names and feed URLs remain editable; website identity is read-only after creation. Default feed-host allowlisting includes all seven publishers. See [NEWS.md](NEWS.md) for the endpoints and normalization rules.

## Automatic news scanning is off (v0.1.12)

`NEWS_AUTO_SCAN_ENABLED=false` is the default in settings, Compose, and `.env.example`. The updater may restart the worker, but it remains idle without requesting feeds until explicitly enabled. Change the value in `.env` and recreate `news_scanner` to apply it. Manual `docker compose exec web python manage.py scan_news` remains available and retains baseline/source restrictions. See [NEWS.md](NEWS.md).

## Shared application styles

Keep first-party CSS under `library/static/library/`: `shared.css` contains shared typography/components, `app.css` the consultant layout, and `public.css` the public submission layout. Page roots use the single `library/styles.html` include. Reuse these rules rather than adding inline CSS or parallel component definitions; see AGENTS.md for the DRY working agreement.

## Shared record browsers (v0.2.2)

Use the normal updater after the UI PRs are merged. This release requires no new migrations or configuration. Assessment actions, evidence/findings, and contacts reuse the inventory table/preview components and common stylesheet. Existing data, permissions, forms, CSRF checks and historical snapshots remain in place.

## Contact ownership (v0.2.3)

The normal updater applies two owner/notes migrations. Five former text fields become optional protected contact references: inventory item owner, inventory information-follow-up owner, action investigation owner, evidence-request owner, and remediation-task owner. They all have a separate Notes field. As agreed for this synthetic deployment, no existing named owners require conversion; blank/Unassigned values become empty contact references. A migration refuses unexpected meaningful text rather than guessing names or silently deleting that information. No legacy-owner columns or reconciliation UI are added; historical JSON captures and audit details remain untouched.

This release also carries the approved v0.2.2 shared record-browser changes from PR #11, which had been merged into the former inventory feature branch after PR #10 reached main.

## Contextual form controls (v0.2.4)

Use the normal updater; no migrations or configuration are required. The shared Django form renderer provides contextual empty-choice labels and field-help metadata. A shared script presents help dialogs, retaining inline help if JavaScript is unavailable. Admin overrides live in `templates/admin/base_site.html`, loaded through the project template directory; they use the same script and stylesheet.

## Synthetic operation prefill (v0.2.6)

After the normal update, use the Operations tab’s explicit walkthrough action to add missing Harbor Cafe examples. No migrations, startup seeding or scanner changes are involved. Existing local inventory stays intact until the consultant chooses the action; matching records and historical captures are retained.
