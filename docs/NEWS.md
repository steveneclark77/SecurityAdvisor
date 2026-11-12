# Security news ingestion and version history (v0.1.10)

After an approved baseline exists, the daily worker reads enabled RSS/Atom sources and saves article candidates for human review. News is a shared-library workflow, separate from customer findings. Collection does not scan customer systems, establish customer applicability, assign severity, apply remediation, or change controls/baselines/assessments/reports. Every feed article is a candidate, including unrelated news. AI relevance classification and generated recommendations remain future work.

## Sources

Open `/admin/` and use **News > Sources** to configure name, website URL, feed URL, notes, and enabled status. Disable a source to stop fetching; its history remains. Initial migration creates:

| Source | Website | Initial feed |
| --- | --- | --- |
| The Hacker News | https://thehackernews.com/ | https://feeds.feedburner.com/TheHackersNews |
| Bleeping Computer | https://www.bleepingcomputer.com/ | https://www.bleepingcomputer.com/feed/ |
| Dark Reading | https://www.darkreading.com/ | https://www.darkreading.com/rss.xml |

Verify endpoint availability and reuse terms in your deployment. This cloud environment blocked live feed probes at its outbound proxy; these endpoints have not been validated live here. Update feed URLs when publishers change them. Homepages are references, not HTML scraping targets. The app stores bounded feed excerpts and links, not downloaded full articles.

## Issue identity, versions, and provenance

**Issue** holds permanent discovery identity: original source, URL-derived deduplication hash, first scan, discovery/last-seen dates, and the current-version pointer. Its original source remains the original discoverer even when another publisher supplies later guidance.

**IssueVersion** holds a complete content snapshot: issue, sequential version number, name, article URL, description, publication date, severity, issue type, remediation, identifiers, creation timestamp, actor, change reason, and origin (publisher ingestion, consultant edit, automated proposal, or legacy migration). Severity starts **unknown**, type **unclassified**, and remediation blank. They require consultant judgment; a publisher article is not proof of a customer vulnerability.

**IssueVersionReference** stores one or more supporting publications for each version: source, captured source name/website, exact article/advisory URL, source publication date, and supporting notes. This separates who made the change from the publications supporting it. A user can edit an issue using a different publisher or several publishers. Source renames do not rewrite captured attribution. Supporting URLs must be credential-free HTTPS; they are not fetched automatically.

Every saved version, including the latest, is immutable. To edit, open an issue and choose **Create next version**. The form starts with current content. Enter the new judgment and a change reason. Keep **Keep supporting references from the previous version** selected to inherit citations and optionally add more. Clear it to replace the set with the references entered on the form (which may be empty for an unsupported observation). Enter CVE/CWE/product/version/advisory references in identifiers as appropriate. Save creates the successor and advances the pointer atomically. A save with identical content and references creates no extra version.

The service locks the issue while allocating the next number, enforces unique issue/version numbers, and rejects stale edits instead of overwriting another user's work. Reload the latest version after a stale-edit error. History links on the issue open the exact saved versions and their references. Model/queryset checks and PostgreSQL/SQLite triggers prevent updating/deleting versions and references, changing published reference sets, or moving a current pointer backwards/across issues.

Repeated sightings only update `last_seen_at`. A changed publisher title/excerpt/URL/publication date creates an **automated proposal** version while carrying forward consultant-entered severity, type, remediation, identifiers, and other supporting sources. It requires fresh review; no library changes follow automatically. Automated comparison uses the last publisher observation, so a consultant edit alone does not cause an unchanged feed item to create another version. Different-source articles are not automatically merged: link them as duplicates or cite them when creating the next version.

## Exact-version reviews

Add a **Review** selecting the issue and its current version: add/update/ignore, rationale, proposed guidance, related working controls, and optional duplicate-of issue. Add/update requires proposed guidance. Reviews record actor/time and an issue/reference snapshot. A new version shows **Needs review**; earlier decisions still point to the exact version reviewed. Correct a decision by appending another review. Reviews cannot be edited/deleted through admin, including ignores.

An add/update decision records a reviewed proposal only. Apply approved guidance through the existing working-library and explicit baseline capture/approval workflow. No proposal automatically updates guidance. Sources, issues, scans, versions, references, and reviews cannot be deleted through admin. Standard Django permissions govern global library access; staff status alone grants none. Creating a successor requires both issue-change and issue-version-add permission. Customer isolation remains unchanged.

## Migration and historical records

Existing issue content becomes version 1 with `legacy_migration` origin, original-source attribution, and unknown historical authorship. Existing review JSON is preserved exactly. Such reviews keep a null version link: their snapshots may describe earlier edits, so the app does not falsely identify them as reviews of version 1. Assessments, reports, baselines, approvals, and customer audit records are not rewritten.

Version-history migrations deliberately refuse downgrade. Flattening multiple versions into the old mutable row would lose history; removing the database guards would weaken it. Back up before migrating. To downgrade, restore a reviewed pre-upgrade backup rather than reversing these migrations. The updater stops web and scanner before migrating and restarts them only after successful checks.

## Automatic and manual runs

`./update.command` migrates and restarts `news_scanner` alongside the app. The worker runs immediately, then every 24 hours while Docker is running. It waits without fetching until a baseline is approved. Restarting causes another immediate, deduplicated cycle. Missed days are not replayed, and a daily snapshot can miss entries that age out between runs.

```bash
docker compose logs news_scanner
docker compose exec web python manage.py scan_news
```

For an initial Compose installation, apply migrations before starting the worker, or restart it after migration. The service restarts after startup failure. A one-shot scan exits nonzero if a feed fails or no approved baseline exists. Inspect **News > Scans** for captured feed URL, timestamps, status, new-issue count, and sanitized failure details. Failed feeds retry next cycle; one failure does not prevent other sources from running. A scan left `running` after interruption is not a success. Overlapping scans may create separate audit records, but issue uniqueness and version locking protect content.

Disable sources to pause ingestion persistently, or `docker compose stop news_scanner` to pause until the updater restarts it. No email/notification is sent.

## Network, parser, and storage boundaries

Use trusted public publishers only. `NEWS_ALLOWED_HOSTS` is a comma-separated exact-host allowlist; defaults match the seeded feeds. Set it in `.env` for Compose or in the Python process environment, then recreate web/worker services. The environment's separate outbound policy must also permit the feeds and legitimate redirects.

HTTPS verification and original-hostname SNI remain enabled. Every feed connection resolves the allowed publisher, rejects non-public DNS answers, and pins the socket to a checked public IP. Redirects repeat validation. Inherited proxy/CA settings remain in use. For an HTTP CONNECT proxy, the tunnel target is the checked public IP while TLS verifies the publisher hostname. A proxy that permits only hostname-based CONNECT targets may reject this: configure its approved destination policy appropriately, or run on an approved network without that proxy. The app does not fall back to an unpinned connection or disable TLS.

Responses have a 10-second socket timeout, a checked 30-second read budget, and a 2 MiB size limit. Defused XML rejects entities/external references. Depth (64), node (10,000), and entry (500) limits are checked during parsing. Non-feed responses fail explicitly. Article/reference pages are never fetched automatically. Publisher excerpts are untrusted and escaped by Django admin.

Automatic ingestion also has cumulative quotas, configurable in `.env`/process environment:

| Setting | Default | Behavior at limit |
| --- | --- | --- |
| `NEWS_MAX_ISSUES_PER_SOURCE` | 10,000 | Stop a scan that would add more candidates for that source |
| `NEWS_MAX_AUTO_VERSIONS_PER_ISSUE` | 100 | Stop publisher updates that would exceed this count for an issue |

Quota failures roll back that source's candidate/version writes and record a failed scan. Existing history is never pruned or overwritten. Review storage and source behavior before raising limits; recreate services to apply changes. Consultant edits are not limited by the automatic-version quota. Audit records continue to accumulate and require ordinary database capacity monitoring.

## Validation

`python manage.py test news` covers synthetic feeds, repeated sightings, publisher changes, provenance, immutable rows, stale forms, quotas, parser/connection boundaries, and permissions. An isolated legacy-database migration test verifies content/review preservation and refusal to downgrade. The PostgreSQL suite additionally races two editors to verify that one succeeds and the stale editor is rejected. Chromium/WebKit tests exercise source creation, version/reference creation, disabled incomplete-input buttons, and exact-version review using real CSRF behavior. No test contacts publishers. Live endpoint correctness still requires a separate check on an allowed network.
