# Security news ingestion (v0.1.9)

News collection is a shared-library workflow, separate from customer findings. After an approved baseline exists, the daily worker reads enabled RSS/Atom sources and saves new article candidates for human review. It does not scan customer systems, certify applicability, assign a risk score, apply remediation, or change controls/baselines/assessments/reports. Every feed article is a candidate, including unrelated news; semantic classification and AI-generated recommendations are not implemented.

## Sources and issues

Open `/admin/` and use **News > Sources** to configure name, website URL, feed URL, notes, and enabled status. Disable a source to stop future fetches; existing issues and scans remain. Source names are unique. Initial additive migration creates:

| Source | Website | Initial feed |
| --- | --- | --- |
| The Hacker News | https://thehackernews.com/ | https://feeds.feedburner.com/TheHackersNews |
| Bleeping Computer | https://www.bleepingcomputer.com/ | https://www.bleepingcomputer.com/feed/ |
| Dark Reading | https://www.darkreading.com/ | https://www.darkreading.com/rss.xml |

These feed endpoints must be verified in your deployment: publisher endpoints, access rules, availability, and reuse terms can change. This development environment blocked live probes at its outbound proxy; the seeded endpoints have not been validated live here. Update feed URLs in admin when needed. Homepages are reference URLs, not HTML scraping targets. Only short feed-provided excerpts are retained, not downloaded full articles.

**News > Issues** stores the requested name, description, remediation, and severity, plus source, article URL, publication/discovery/last-seen dates, issue type, identifiers, and first scan. Publisher excerpts are unverified text and are escaped by Django admin. Severity starts **unknown**, type **unclassified**, and remediation blank. A consultant records those judgments; an article is not proof of a vulnerability in any customer. CVE/CWE, affected products/versions, and vendor advisory references can be entered in identifiers.

The list shows the latest review decision or **Awaiting review**. Add a **Review** for each candidate: add/update/ignore, rationale, proposed guidance, related working controls, and optional duplicate-of article. Add/update requires proposed guidance. Reviews record actor/time and a snapshot of the issue's then-current classification/remediation. Reviews cannot be edited or deleted through admin; corrections are new reviews, including corrections of ignores. Source/issue/scan deletion is also disabled. Standard Django model permissions govern global library access; staff status alone does not grant these permissions. Customer models and isolation rules are unchanged.

Selecting add/update records a reviewed proposal only. Apply approved guidance through the existing working-library and explicit baseline capture/approval workflow. No proposal automatically updates the library. Cross-source articles retain separate source links; link duplicates during review. Within a source, exact canonical HTTPS article URLs (fragment removed) deduplicate repeated runs, even if the feed GUID changes. First-observed excerpts remain preserved; subsequent publisher edits and URL/query variations are not automatically reconciled. This is not a complete news archive: a daily feed snapshot can miss articles that age out between runs.

## Automatic and manual runs

Normal `./update.command` builds and restarts `news_scanner` with the application after migrations. The worker runs immediately on startup, then every 24 hours while Docker is running. It waits without fetching if no approved baseline exists. It retries failed feeds on the next daily cycle, and records one scan per enabled source, including failure status and sanitized error information. One failed feed does not prevent others from being processed. Restarting the worker causes another immediate cycle; article deduplication makes repeated scans safe.

For an initial manual Compose installation, apply migrations before starting the worker (or restart it after migration). The service restarts on startup failure. No scheduler runs while Docker Desktop is stopped, and missed days are not replayed. Inspect:

```bash
docker compose logs news_scanner
docker compose exec web python manage.py scan_news
```

A one-shot scan exits nonzero if a feed fails or no approved baseline exists. Inspect **News > Scans** for source, captured feed URL, timestamps, status, and new-issue count. A scan left `running` after an interrupted process is not a successful scan; rerun safely. Overlapping processes may create separate scan records but database uniqueness prevents duplicate issues.

To pause automatic scanning, disable sources in admin, or `docker compose stop news_scanner`. The updater starts the worker again; disabled source settings persist. No notification/email is sent.

## Network and parser boundaries

Feeds use HTTPS with normal certificate verification, inherited proxy/CA settings, 10-second socket timeout, 30-second checked read budget, a 2 MiB response limit, and a 500-entry limit. Defused XML rejects entities and external references. Non-feed responses fail explicitly. Article links must be credential-free HTTPS; article pages are never fetched. Redirect destinations must pass the same feed checks as the original URL.

Feed fetch hosts must be listed in `NEWS_ALLOWED_HOSTS` (comma-separated exact hostnames). Defaults match the three seeded feeds. Set this variable in `.env` for Compose, or the process environment for Python-only use, and recreate the web/worker services after changing it. Only allow trusted public publishers: a public DNS preflight rejects private/non-global answers, but DNS is also resolved by the HTTP client/proxy, so the allowlist and deployment egress controls are the trust boundary against DNS rebinding. Do not add user-controlled or internal hostnames. The application does not weaken the environment's separate outbound policy: allow feed hosts and any legitimate redirect hosts there as well. Never add credentials to source URLs or disable TLS verification.

## Validation

`python manage.py test news` uses synthetic RSS/Atom fixtures and mocked transport; it never contacts publishers. The standard browser suite exercises source creation, issue triage, and append-only review with real CSRF behavior. Existing PostgreSQL and Chromium/WebKit CI jobs include the new code. Publisher access and endpoint correctness require a separate live check on a network that permits these feeds.
