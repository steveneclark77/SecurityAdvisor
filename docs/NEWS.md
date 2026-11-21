# Security news collection, analysis and review (v0.2.13)

Collection captures RSS/Atom articles and immutable revisions, separate from underlying issues. Optional OpenAI analysis extracts suggested defaults and potential duplicate matches into **pending proposals**. All proposals require human acceptance; automatic collection and automatic analysis are independently **off by default**. Neither process changes controls, baselines, customer assessments, findings or reports. This remains a synthetic-data development application.

## Sources

Open `/admin/` and use **News > Sources** to configure name, website URL, feed URL, notes, and enabled status. Disable a source to stop fetching; its history remains. Migrations seed these seven sources by website URL:

| Source | Website | Initial feed |
| --- | --- | --- |
| The Hacker News | https://thehackernews.com/ | https://feeds.feedburner.com/TheHackersNews |
| Bleeping Computer | https://www.bleepingcomputer.com/ | https://www.bleepingcomputer.com/feed/ |
| Dark Reading | https://www.darkreading.com/ | https://www.darkreading.com/rss.xml |
| CISA | https://www.cisa.gov/ | https://www.cisa.gov/cybersecurity-advisories/all.xml |
| UpGuard | https://www.upguard.com/blog | https://www.upguard.com/blog/rss.xml |
| Schneier on Security | https://www.schneier.com/ | https://www.schneier.com/feed/atom/ |
| SecurityWeek | https://www.securityweek.com/ | https://www.securityweek.com/feed/ |

The website `url` is the actual database primary key, not a separate numeric ID or a name. All issue, scan, and supporting-reference foreign keys now use this URL. Names are labels and may repeat. Website URLs are normalized before ordinary saves: HTTPS/lowercase host, omitted default port, no fragment, root slash retained, and trailing slashes removed from non-root paths. Queries, credentials, and non-HTTPS identities are rejected. Database primary-key enforcement rejects duplicate URLs; normal forms also reject normalized duplicates. Different host aliases, redirects, and distinct paths are not automatically merged.

A saved website URL is permanent and read-only in admin, while its name, feed URL, notes, and enabled flag remain configurable. Create a separate source if the website identity changes; disable the old record to retain provenance. Old numeric IDs are retained as read-only `legacy_id` values for migrated sources. Existing JSON/audit records retain their original values, and source admin history includes actions recorded under either identity.

Verify endpoint availability and reuse terms in your deployment. This cloud environment blocked live feed probes at its outbound proxy; these endpoints have not been validated live here. Update feed URLs when publishers change them. Homepages are references, not HTML scraping targets. The app stores bounded feed excerpts and links, not downloaded full articles.

## Issue identity, versions, and provenance

**Issue** holds permanent discovery identity: original source, first scan, discovery/last-seen dates, and the current-version pointer. Legacy URL-derived identities remain unchanged. New accepted analysis proposals receive a permanent identity independent of the article URL, so several articles can support one issue and one article can describe several issues. Its original source remains the original discoverer even when another publisher supplies later guidance.

**IssueVersion** holds a complete content snapshot: issue, sequential version number, name, article URL, description, publication date, severity, issue type, remediation, identifiers, creation timestamp, actor, change reason, and origin (publisher ingestion, consultant edit, automated proposal, or legacy migration). Model defaults remain **unknown** severity, **unclassified** type, and blank remediation until established; accepted analysis proposals can supply consultant-reviewed values. They require consultant judgment; a publisher article is not proof of a customer vulnerability.

**IssueVersionReference** stores one or more supporting publications for each version: source, captured source name/website, exact article/advisory URL, source publication date, and supporting notes. This separates who made the change from the publications supporting it. A user can edit an issue using a different publisher or several publishers. Source renames do not rewrite captured attribution. Supporting URLs must be credential-free HTTPS; they are not fetched automatically.

Every saved version, including the latest, is immutable. To edit, open an issue and choose **Create next version**. The form starts with current content. Enter the new judgment and a change reason. Keep **Keep supporting references from the previous version** selected to inherit citations and optionally add more. Clear it to replace the set with the references entered on the form (which may be empty for an unsupported observation). Enter CVE/CWE/product/version/advisory references in identifiers as appropriate. Save creates the successor and advances the pointer atomically. A save with identical content and references creates no extra version.

The service locks the issue while allocating the next number, enforces unique issue/version numbers, and rejects stale edits instead of overwriting another user's work. Reload the latest version after a stale-edit error. History links on the issue open the exact saved versions and their references. Model/queryset checks and PostgreSQL/SQLite triggers prevent updating/deleting versions and references, changing published reference sets, or moving a current pointer backwards/across issues.

Repeated article sightings update last-seen time without creating content versions. Changed title/excerpt/publication date creates or reuses an immutable **ArticleRevision** and advances the article's current-revision pointer. Publisher changes never advance an accepted IssueVersion. The source/article-URL hash deduplicates publications; issue matching is a separate review step. Migration captures existing publisher-derived issue versions as article revisions and retained associations without rewriting the original issues, versions, references or reviews.

## Analysis pipeline and manual CLI

1. Capture feeds with `scan_news` as before. A baseline approval is still required for collection. Each publication appears in **News > Articles**, including its numeric Article ID and current revision.
2. Queue current article revisions for a configured model/prompt/schema policy. A revision is queued once per policy unless an explicit retry is requested after failure (default maximum three attempts). Successful zero-issue analyses also count as analyzed.
3. The analyzer sends only the public title/excerpt and up to 20 shared-library candidate issues. Exact CVE identifiers and bounded title-keyword retrieval find candidates; embeddings, broad semantic search and full-article fetching are deferred. Every proposed match remains unconfirmed until human review, regardless of confidence.
4. Validate structured output: at most five extracted issues, known severity/type enums, bounded fields, evidence passages that occur in the article, and identifiers present in that text. Unsupported severity remains Unknown and remediation may remain blank. Capture affected products/versions, provenance basis, rationale, uncertainty and confidence. Model confidence is not an automation permission.
5. Save **AnalysisRun**, immutable **AnalysisResult**, and immutable **IssueProposal** records. The claimed run retains the exact public input/candidate snapshot, provider/model, full prompt/schema, pricing assumptions, timestamps, usage and conservative budget reservation. Completed runs and content history are database-protected against update/delete. Invalid output fails atomically without publishing partial proposals.
6. Review in admin. Acceptance is the only path from proposals to issues; see below.

### Configure without enabling automatic analysis

Set these in the local `.env` (never commit it):

```dotenv
NEWS_ANALYSIS_ENABLED=false
NEWS_ANALYSIS_API_KEY=your-provider-key
NEWS_ANALYSIS_MODEL=gpt-4.1-mini
NEWS_ANALYSIS_MAX_ATTEMPTS=3
NEWS_ANALYSIS_PER_RUN_CENTS=25
NEWS_ANALYSIS_DAILY_CENTS=500
NEWS_ANALYSIS_INPUT_PRICE=1
NEWS_ANALYSIS_OUTPUT_PRICE=5
```

`NEWS_ANALYSIS_MAX_ATTEMPTS` accepts 1–10 (default 3). The provider is currently OpenAI at the fixed HTTPS `api.openai.com/v1/chat/completions` endpoint; model must support strict JSON-schema output. Prices are configurable **USD per million tokens**, and are conservative estimates, not a provider billing guarantee. Confirm pricing for the selected model and set a provider-side account spending limit too. The API key is passed only to the analyzer service, not web/scanner. Analysis sends public shared-library content to the configured provider; do not put customer secrets in these records. Allow `api.openai.com` in deployment outbound policy; TLS verification and inherited proxy/CA settings remain enabled. No live provider request is made during tests or installation.

### Analyze one, some, or all unanalyzed records manually

Use **Article IDs**, not Issue IDs. These commands work while `NEWS_ANALYSIS_ENABLED=false`:

```bash
# One article:
docker compose run --rm news_analyzer python manage.py analyze_news --article 12

# Selected articles:
docker compose run --rm news_analyzer python manage.py analyze_news --article 12 18 23

# All current revisions not already analyzed/queued under this policy, in batches:
docker compose run --rm news_analyzer python manage.py analyze_news --all-unanalyzed --drain --max-records 500

# Queue without an API call/key, then explicitly process queued work:
docker compose run --rm news_analyzer python manage.py analyze_news --article 12 18 --queue-only
docker compose run --rm news_analyzer python manage.py analyze_news --queued

# Explicitly retry failures; never implicitly rerun successful analysis:
docker compose run --rm news_analyzer python manage.py analyze_news --all-unanalyzed --retry-failed
```

`--max-records` defaults to 50 and accepts 1–500. Add `--drain` to process every selected eligible revision in successive bounded batches until complete or a budget/error stops the command; without it, only one batch runs. It analyzes each selected article's **current revision**, not every historical revision. Pending jobs for the selected articles can be processed without requeueing them. With `--queued`, current-policy pending jobs are processed by creation order. Failed jobs require `--retry-failed`; interrupted jobs older than five minutes become retained failures at the next processing cycle. Retries are new retained attempts and consume another reservation. Preflight failures such as missing credentials or exhausted budgets leave jobs queued and return an actionable CLI error without sending a request.

In Python-only deployments, export the same settings and use `python manage.py analyze_news ...`. Settings do not automatically read `.env` outside Compose.

### Review, edit, consolidate, and correct

Open **News > Issue proposals**, inspect its suggested fields/matching evidence, and choose **Review**. The review screen shows the captured evidence and previous issue content. Select a candidate issue to consolidate coverage, or **Create a new issue**. The default is the proposed match, if any. Use **Search issues by name or identifier** above the review form to add up to 20 matching issues to the target selection. Search before editing, because it reloads the proposal defaults.

Choose Accept, Reject or Supersede, enter rationale, and edit the suggested name, description, severity, type, remediation and identifiers as needed. Acceptance requires explicit issue/version/link permissions (and issue-add permission for a new issue). Signed candidate-version snapshots and row locks prevent overwriting intervening edits; reload after a stale-review error. New-issue acceptance rechecks CVEs against existing issues under a shared creation lock so concurrent publisher reports are not accepted as separate CVE issues. Ambiguous historical duplicate CVEs require consultant judgment rather than automatic merging.

Accepting creates a normal consultant-authored immutable IssueVersion, adds publisher references, and records a confirmed **IssueArticleLink**. A no-op with unchanged content/references reuses the current version. The analysis output/proposal remains unchanged. Reject/Supersede records the decision without creating an issue. These decisions are retained; none applies library guidance automatically. Continue using the existing exact-version Review and baseline workflow for actual control-library changes.

To correct accepted content later, use **Create next version** on the issue. To correct a mistaken association, add an **Issue article link** with relationship **Retracts association** and a rationale; add a Supports event for the correct issue. The latest event for that issue/article determines association-based future candidate retrieval. Earlier association events and issue-version citations remain intact; correct current citations through another issue version if needed. Shared identifiers or title similarity may still independently retrieve an issue as a review candidate.

### Optional automatic worker and limits

`./update.command` also builds/restarts `news_analyzer`. It remains idle without database or provider requests unless `NEWS_ANALYSIS_ENABLED=true`. To opt in later, set that value in `.env` and recreate it with `docker compose up -d --force-recreate news_analyzer`. It checks for pending/new current revisions every 60 seconds in bounded batches. It never accepts proposals or automatically retries failed calls. The scanner's separate daily schedule and default-off setting are unchanged.

Requests run in a network-only subprocess, killed/reaped at a 60-second overall deadline, with a 30-second socket timeout and a 1 MiB provider-response limit. Input is capped at 60,000 encoded bytes; output is capped at 4,000 tokens. Redirects are rejected; there is no configurable arbitrary provider URL, article fetching, tool execution or access to customer models. Public text is untrusted evidence, never instructions.

Before each call, the worker validates a worst-case estimate and atomically reserves the **full per-run cap** against the UTC day's shared budget. Reservations are deliberately not refunded, including failures/timeouts, because billed usage may be unknown. Stored result costs use configured price estimates. Attempts, provider output and proposals are retained; no historical pruning is performed. Monitor database capacity and provider billing. `docker compose logs news_analyzer` and **News > Analysis runs** show status; sanitized failures never retain API keys or raw error responses.

## Exact-version reviews

Add a **Review** selecting the issue and its current version: add/update/ignore, rationale, proposed guidance, related working controls, and optional duplicate-of issue. Add/update requires proposed guidance. Reviews record actor/time and an issue/reference snapshot. A new version shows **Needs review**; earlier decisions still point to the exact version reviewed. Correct a decision by appending another review. Reviews cannot be edited/deleted through admin, including ignores.

An add/update decision records a reviewed proposal only. Apply approved guidance through the existing working-library and explicit baseline capture/approval workflow. No proposal automatically updates guidance. Sources, issues, scans, versions, references, and reviews cannot be deleted through admin. Standard Django permissions govern global library access; staff status alone grants none. Creating a successor requires both issue-change and issue-version-add permission. Customer isolation remains unchanged.

## Migration and historical records

Existing issue content becomes version 1 with `legacy_migration` origin, original-source attribution, and unknown historical authorship. Existing review JSON is preserved exactly. The URL-key migration transfers every source relationship atomically while retaining source-name/website snapshots. If pre-existing websites normalize to a duplicate URL, it stops with their old IDs rather than merge or discard history. Correct those records after reviewing their relationships, then rerun the updater.

Such reviews keep a null version link: their snapshots may describe earlier edits, so the app does not falsely identify them as reviews of version 1. Assessments, reports, baselines, approvals, and customer audit records are not rewritten.

Version-history migrations deliberately refuse downgrade. Flattening multiple versions into the old mutable row would lose history; removing the database guards would weaken it. Back up before migrating. To downgrade, restore a reviewed pre-upgrade backup rather than reversing these migrations. The updater stops web and scanner before migrating and restarts them only after successful checks.

## Automatic and manual runs

`./update.command` migrates and restarts `news_scanner` alongside the app. Automatic scanning defaults to **off** (`NEWS_AUTO_SCAN_ENABLED=false`). The worker stays idle without database queries or feed requests while off. With explicit opt-in it runs immediately, then every 24 hours while Docker is running. It waits without fetching until a baseline is approved. Restarting causes an immediate, deduplicated cycle only when automatic scanning is enabled. Missed days are not replayed, and a daily snapshot can miss entries that age out between runs.

To enable automatic scans later, set `NEWS_AUTO_SCAN_ENABLED=true` in `.env` and recreate the worker with `docker compose up -d --force-recreate news_scanner`. To disable it, set the value back to `false` and recreate the worker again. Only the literal `true` (case-insensitive, surrounding whitespace ignored) enables automatic requests. The setting persists across updater runs; an absent setting defaults off. Python-only deployments use the same process environment variable and must restart the worker after changes.

Manual one-shot scans remain available while automatic scanning is off. They still require an approved baseline, respect per-source enabled flags, and retain the same network and storage limits:

```bash
docker compose logs news_scanner
docker compose exec web python manage.py scan_news
```

For an initial Compose installation, apply migrations before starting the worker, or restart it after migration. The service restarts after startup failure. A one-shot scan exits nonzero if a feed fails or no approved baseline exists. Inspect **News > Scans** for captured feed URL, timestamps, status, new-article count, and sanitized failure details. When automatic scanning is enabled, failed feeds retry next cycle; one failure does not prevent other sources from running. A scan left `running` after interruption is not a success. Overlapping scans may create separate audit records, but issue uniqueness and version locking protect content.

Use the global setting to keep all automatic ingestion off. Per-source enabled flags additionally select which sources may be scanned, including by manual runs. `docker compose stop news_scanner` pauses the worker until the updater restarts it, but does not change the persistent setting. No email/notification is sent.

## Network, parser, and storage boundaries

Use trusted public publishers only. `NEWS_ALLOWED_HOSTS` is a comma-separated exact-host allowlist; defaults match the seeded feeds. Set it in `.env` for Compose or in the Python process environment, then recreate web/worker services. The environment's separate outbound policy must also permit the feeds and legitimate redirects.

HTTPS verification and original-hostname SNI remain enabled. Every feed connection resolves the allowed publisher, rejects non-public DNS answers, and pins the socket to a checked public IP. Redirects repeat validation. Inherited proxy/CA settings remain in use. For an HTTP CONNECT proxy, the tunnel target is the checked public IP while TLS verifies the publisher hostname. A proxy that permits only hostname-based CONNECT targets may reject this: configure its approved destination policy appropriately, or run on an approved network without that proxy. The app does not fall back to an unpinned connection or disable TLS.

Network fetching runs in a separate Python worker without loading application models or opening database connections. The parent enforces a 30-second overall deadline, kills and reaps a blocked worker on timeout, and records the source failure before continuing to later sources. This deadline covers DNS resolution, redirects, connection/TLS setup, response headers, and body reads; it does not depend on the network call returning first. The worker also retains a 10-second socket timeout and a 2 MiB response limit. Proxy/CA settings are inherited, and HTTPS pinning/verification remain enabled. Defused XML rejects entities/external references. Depth (64), node (10,000), and entry (500) limits are checked during parsing. Non-feed responses fail explicitly. Article/reference pages are never fetched automatically. Publisher excerpts are untrusted and escaped by Django admin.

Automatic ingestion also has cumulative quotas, configurable in `.env`/process environment:

| Setting | Default | Behavior at limit |
| --- | --- | --- |
| `NEWS_MAX_ISSUES_PER_SOURCE` | 10,000 | Stop a scan that would add more articles for that source |
| `NEWS_MAX_AUTO_VERSIONS_PER_ISSUE` | 100 | Stop capture that would exceed this many distinct revisions of an article |

Quota failures roll back that source's article/revision writes and record a failed scan. Existing history is never pruned or overwritten. Review storage and source behavior before raising limits; recreate services to apply changes. These legacy-named settings now bound article capture; consultant issue edits are not limited by them. Audit records continue to accumulate and require ordinary database capacity monitoring.

## Validation

`python manage.py test news` covers synthetic feeds, repeated sightings, publisher changes, provenance, immutable rows, stale forms, quotas, parser/connection boundaries, and permissions. Isolated migration tests run on the selected database backend, verify source-key conversion and content/review preservation, and check that duplicate websites stop migration without removing history guards. They create and destroy only temporary test databases. The PostgreSQL suite additionally races two editors to verify that one succeeds and the stale editor is rejected. Chromium/WebKit tests exercise source creation, version/reference creation, disabled incomplete-input buttons, and exact-version review using real CSRF behavior. No test contacts publishers. Live endpoint correctness still requires a separate check on an allowed network.
