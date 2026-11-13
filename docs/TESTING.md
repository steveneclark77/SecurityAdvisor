# Application and browser regression checks

All fixtures are synthetic. Django creates and destroys a dedicated test database; no test command starts an engagement against a real company. Browser uploads use temporary private storage.

## Server-side suite

Run `python manage.py test` in the configured development environment, or `docker compose exec web python manage.py test`.

The CSRF matrix enables Django's real CSRF enforcement for every application POST route. For 45 form operations, including intake draft/final submission and evidence response, it verifies:

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

Feed-deadline regression tests start a real blocked synthetic child process, verify it is killed and reaped at the overall deadline, verify successful payload transfer, and check that a failed source does not prevent later sources from being scanned. Transport validation/pinning/parser/quota tests remain in place.

## Shared styles and DRY

`python manage.py test testsupport.test_styles` checks every first-party template for embedded style blocks and style attributes. All page roots use `library/styles.html`, which loads `shared.css` plus the relevant `app.css` or `public.css` layout. Typography, validation errors, guidance panels, and print guidance have one shared definition. The browser suite checks stylesheet loading on consultant and public pages, responsive table spacing, print visibility, and the submission confirmation panel.

## Engagement journey UI

`python manage.py test engagements.test_journey` verifies recommendation/status derivation, optional intake, unknown/archived inventory, immutable GET behavior, safe area selection, and assignment checks for superusers. The CSRF submission inventory selects the relevant work pane through the read-only `area` query parameter; mutating endpoints and their payload/outcome checks are unchanged. Browser coverage verifies the seven unique rail actions, equal button styling, noninteractive preparation guidance, smaller connector arrowheads, arbitrary-order navigation, and mobile layout without horizontal overflow. Synthetic desktop/mobile screenshots are captured with the browser artifacts.

## Inventory explorer

Inventory tests cover preserved filters, category counts, archived visibility, empty types, pagination, invalid navigation parameters, read-only GETs, and assignment-scoped selection including superusers. The real-browser explorer test covers type navigation, contextual Add, table selection and preview, search empty/recovery states, relationships/follow-ups, and mobile overflow. CI artifacts include `inventory-desktop.png` and `inventory-mobile.png` for each browser engine. Existing inventory form submissions remain in the CSRF matrix.

## Shared assessment, evidence and contact browsers

`python manage.py test engagements.test_browsers inventory testsupport.test_styles` verifies frozen instructions, filters, pagination, invalid/foreign selections, full-name search, read-only GETs, customer assignment for superusers, contact-management/reuse boundaries, retained inactive links and archived records. The existing action-verification regression now explicitly selects the action whose observation is checked. The CSRF submission inventory explicitly selects the evidence request whose scoped link is submitted.

The shared real-browser test covers assessment filters/selection, all three evidence collections, single creation/edit entry points, contact link vs shared-person actions, accessible form labels, search, and preview navigation without page overflow at mobile widths. The inventory browser test also exercises the common table/layout after refactoring. Browser CI artifacts include `assessment-desktop.png`, `evidence-findings-desktop.png`, `contacts-desktop.png` and corresponding mobile screenshots, alongside the inventory screenshots. Both Chromium and WebKit remain required CI jobs.

Common table, filter and pagination templates live in `library/templates/library/components/`; safe URL/pagination/selection helpers live in `library/record_browser.py`. Callers must supply already-authorized querysets. Reusable layout/component styles live in `library/static/library/shared.css`; page widths and engagement workspace layout remain in `app.css`. Entity-specific previews and permission checks stay in their owning app. No client-side rendering framework or CSS injection is involved.

## Contact ownership

`python manage.py test engagements.test_ownership engagements.test_owner_migration` checks all five owner forms, model-level eligibility, foreign-ID rejection, scope through the same active relationship, current archived-owner retention, deletion protection, notes persistence, owner-name snapshots, assigned-superuser restrictions, and the customer-scoped contact creation branch. The isolated migration test checks actual schema conversion, retained records/snapshots/audit JSON and refusal of unexpected text owners on SQLite/PostgreSQL. The existing news migration tests reuse the isolated database harness now located in `testsupport/migration_database.py`.

The real-browser ownership test adds a contact in a new tab, links its role, refreshes the original owner dropdown, verifies unsaved notes survive, selects one owner and saves inventory and an evidence request. The existing CSRF matrix now submits actual contact IDs for owners; all mutation routes and CSRF enforcement remain in place. Owner choices refresh through an authorized, read-only, uncached GET endpoint. The shared picker script creates text-only options and controls; all styles remain in the shared stylesheet.

## Contextual choices and field-help dialogs

`python manage.py test library.test_form_rendering testsupport.test_styles` checks contextual blank choices, preservation of explicit filter/unknown values, escaped field metadata and the shared CSS rule across app and project-level templates. The browser suite verifies operation-category/owner labels; visible Add contact and icon-only refresh; help without submitting an incomplete form; dialog Escape/Close and focus return; hidden inline help; one icon per checkbox group; public intake help; admin help and dynamically added inline fields. Existing full browser form/CSRF tests continue to exercise legitimate submissions and browser headers. A synthetic `contextual-form-help.png` screenshot is included in browser artifacts.

## Inventory cancellation and control sizing

Inventory navigation tests check safe customer-scoped return destinations and explorer edit links. The browser cancellation test edits name/notes, cancels back to the filtered list, and verifies unchanged persisted fields/history. It also verifies Cancel remains available on an invalid new-record form. Geometry checks compare the owner select, Add contact, refresh, Save and Cancel heights, and verify a roughly 17px info circle inside a 24px clickable button. Existing responsive/print and full form/CSRF browser checks remain in place.

The light-elevation browser check verifies the shared white/charcoal/border/shadow treatment on inventory actions, public submission buttons and admin Save, including hover, keyboard focus and disabled appearance. Layout stylesheets no longer define competing button colors.

## Full synthetic inventory prefill (v0.2.7)

`python manage.py test inventory.test_walkthrough` covers all seven kinds, 18 example items, 15 relationships and eight follow-ups; optional scoped owners; unknown/unrated state; audited creation; and repeated calls after editing, renaming, archiving or resolving records. It verifies earlier v1 operation-marker compatibility, kind-aware matching, skipped ambiguous/archived endpoints, snapshot retention, synthetic-only access, assigned-superuser restrictions and forged-owner rollback.

The same protected action remains in the CSRF inventory (45 form operations), with valid contact-ID submission and missing/invalid token/origin rejection. The browser test opens the full-inventory prefill, chooses an owner, checks examples across the kinds and repeats without new records/audits. Existing authenticated-form browser coverage also exercises the new action. No live systems are scanned and no real personal/payment information is used.

## Persistent headers (v0.2.8)

The real-browser header regression checks sticky position on long consultant, public and admin forms; mobile Menu visibility/expanded state; Enter/Tab/Escape navigation and focus return; stable header height while Menu opens; 320px overflow; hash/field clearance; retained admin logout CSRF token; and print hiding. Admin's page container must grow with long content so it does not constrain the sticky header. Existing form/CSRF and responsive/print tests still run on both browser engines. Synthetic `persistent-admin-mobile.png` is included with browser artifacts.

A shared header partial serves consultant/public pages; admin preserves Django's original account/logout markup. Shared CSS owns positioning, menu layout and scroll clearance. `header.js` toggles classes/ARIA state and reveals obscured focus/anchor targets without injecting styles. With JavaScript unavailable, navigation stays visible instead of becoming inaccessible.

## Table sorting and view controls (v0.2.9)

`python manage.py test library.test_table_sorting` verifies natural name/quantity ordering across more than one page, sort/filter/selection links, displayed owner/state values, unsortable action columns, malformed/oversized sort tokens, very long numeric text, read-only GET behavior and unchanged legacy review display. Only known column indexes are accepted; sort parameters never become ORM field names or SQL.

The browser regression checks both server-sort header links and rendered relationship-table sorting, ascending/descending ARIA state, excluded action columns, absence of info controls on inventory/contacts/library/admin search/filter controls, retained Notes help and native admin computed-column sort links. Existing full form and CSRF browser checks remain unchanged. Native Django admin changelists retain server ordering; its previously computed issue-name/review-status and baseline-status columns now provide ordering metadata.

Paginated record browsers sort the filtered, authorized result by displayed values before pagination, including computed roles/state/quantity columns; unsorted views keep queryset pagination. Sorting evaluates the scoped filtered result in memory. Other fully rendered data/detail/report tables use the shared `tables.js` enhancement without changing saved data. Data-entry inline-form layouts are not reordered. Detail tables receive Field/Value headings; action columns and empty-state rows are excluded. All sort styles are in shared CSS. View-control GET forms and admin bulk-action controls do not get field-help dialogs; POST data-entry fields keep them.
