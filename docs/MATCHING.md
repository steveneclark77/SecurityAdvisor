# Learning, calibrated matching, and reviewer notifications (v0.2.14)

Article extraction still uses the public-news analysis described in [NEWS.md](NEWS.md).
Matching is a separate, cached stage. Initial mode is **learning**: every existing/new
incident judgment needs a human. Installing or updating never enables autonomy.
`NEWS_ANALYSIS_ENABLED=false` still keeps the analyzer and matching loops idle.

## Reviewer role and inbox

Assign active accounts to the Django group **security-news reviewers**. The group is
created empty on migration, with the news permissions needed for review. Existing
group permission customizations are not overwritten. Membership is explicit even
for superusers; ordinary staff status alone does not give inbox access. Existing
customer assignment rules, including those for superusers, are unchanged.

Members see **News inbox** in the app header, with a personal unread count. The inbox
contains new-issue notices, matching work, and automatic duplicate-source links.
Marking a notice read affects only that user. Resolved matching work leaves the
unread task view for everyone; Show read notifications retains the full event history.
Search and sort controls are view controls, without field-help icons.

Open a pending item and inspect the source excerpt, comparison evidence and proposed
route. Decide:

- **Same incident**: choose an existing issue and explain why. This appends a source
  association and leaves its severity, remediation and content version unchanged.
- **New incident**: review/edit proposed defaults, then create the issue.
- **Not a security issue**: retain the negative judgment without creating an issue.
- **Still uncertain**: retain the judgment for later review; do not teach uncertainty
  as a positive or negative example.

Use Search issue names or identifiers before editing to include another issue in
the bounded target list. Saving a correction appends feedback and retracts a wrong
prior association; it does not delete an issue, article, decision or old version.
Reaffirming a previously created new incident reuses that incident instead of
creating it again. Required action inputs are enforced in browser and server.

An issue's **Reports** page shows active article associations, their publisher names
as captured, and source links. Show association history recalls prior revisions,
retractions, human confirmations and automatic links. Existing staff editing and
Create next version remain available for issue content. Accepting a content proposal
with a definite existing/new issue choice also records that group member's identity
judgment. Rejecting remediation advice is **not** treated as rejecting the incident.

## What is cached

| Cache / record | Key and invalidation |
| --- | --- |
| Article extraction | Existing immutable analysis result per article revision and analysis policy. Matching never re-runs this LLM extraction merely because feedback/calibration changed. |
| Issue identity profile | Issue, immutable source issue-version ID, hash of normalized name/description/type/identifiers/products/affected versions. Severity/remediation-only edits reuse identity and embedding. |
| Indexed match keys | Normalized CVE/advisory IDs, product names and title tokens. Rebuilt only on identity change. |
| Embedding | Content hash + embedding model + dimensions (256). Stored once and shared across identical content; failed attempts and budget reservations retained. |
| Semantic index | Eight indexed deterministic locality-sensitive hash bands per normalized vector. Retrieves candidates without loading every DB vector into Python. |
| Pair comparison | Extraction identity hash + issue identity hash + matching policy + embedding keys. Retains features, immutable source version ID and structured identity fields for audit. |
| Assessment | Proposal, catalog generation, calibration version, candidate comparison keys and completeness. A catalog or calibration change can rescore cached data without new article analysis. |

Candidate retrieval combines indexed identifiers/products/tokens and semantic LSH
neighbors, with at most 200 scored candidates. Semantic retrieval is approximate,
not an exhaustive guarantee. Calibration evaluates the resulting decision pipeline,
including retrieval misses. A limit hit, stale profile, missing embedding, unknown
calibration bin, or insufficient evidence prevents autonomy. Contradictory identifiers
and product facts block automatic linking; equal plausible matches remain ambiguous.
The latest historical article-association events are separately retained.

Embeddings use OpenAI `text-embedding-3-small` by default. Requests use the existing
fixed-host, TLS-verified, bounded subprocess transport, with no article fetching or
tools. Input limit is 40,000 bytes; dimension and finite numeric output are validated.
The model setting, dimensions and content hashes identify caches. Embedding calls
reserve `NEWS_EMBEDDING_PER_RUN_CENTS` against the **same UTC daily budget** as article
analysis. `NEWS_EMBEDDING_INPUT_PRICE` is an estimated USD/million tokens; update it
for the selected model. Reserves are conservative and not refunded after failure.
Attempts are capped by `NEWS_ANALYSIS_MAX_ATTEMPTS`. Provider billing limits remain
important because local prices are estimates, not a billing guarantee.

## Prepare and process manually

Configure the analysis key/pricing in `.env` as in NEWS.md. These commands do not
change the autonomy switch:

```bash
# Capture/extract articles first; automatic analysis may stay off.
docker compose run --rm news_analyzer python manage.py analyze_news --all-unanalyzed --drain

# Prepare a bounded batch of missing issue/article embeddings and assess proposals.
docker compose run --rm news_matcher python manage.py match_news --prepare-cache --max-records 50

# Rescore using existing caches only; no provider calls.
docker compose run --rm news_matcher python manage.py match_news --max-records 50
```

Repeat bounded cache preparation to finish a larger catalog. Work rotates past
incomplete rows and resumes from indexed missing profiles, rather than repeatedly
analyzing the same incident. Early judgments made before cache coverage is complete
are retained but excluded from confidence calibration. For useful training examples,
prepare the caches before reviewers make decisions. Existing pre-learning history
is preserved; historical accept/reject content reviews are not guessed into labels.

When `NEWS_ANALYSIS_ENABLED=true`, the analyzer and matcher workers process separate
stages; the matcher checks every minute. This enables processing, **not autonomy**.
The updater builds/stops/restarts both workers around migrations.

## Calibration and explicit admin activation

Human matching judgments are append-only labels. Automated outcomes never label
themselves. The most recent human judgment for a proposal supersedes earlier labels
for evaluation, while keeping their audit history. A match to an issue created after the assessment is excluded because that issue
could not have been retrieved then. Negative/irrelevant judgments
count against a positive new/match prediction. Uncertain judgments are excluded.

Build a version in admin under **Calibration versions**, or:

```bash
docker compose run --rm news_matcher python manage.py calibrate_news \
  --name 'Reviewed matching evaluation 1' --admin YOUR_ADMIN_USERNAME
```

This creates a report; it neither activates it nor enables autonomy. Each feature
bin includes proposed route, identifier agreement, similarity/margin ranges, input
facts, issue kind, and index completeness. Splits are stable and grouped by the
human-confirmed incident, so articles about one incident cannot occur in both
training and held-out sets or inflate sample counts. Multiple observations of the
same incident/bin count as one incident and a miss makes that incident a failure.

A bin needs at least **30 distinct incidents in each split** and a minimum **95%
Wilson lower bound of 0.90** on correct decisions in both training and held-out
results. Thirty all-correct cases alone do not meet that bound; the actual sample
requirement can therefore be higher. This is an empirical conservative confidence
estimate, not an embedding similarity or the model claiming "90% sure". Unsupported
bins continue to need a human, regardless of the global autonomy switch.

An active app superuser must explicitly select the evaluated version and check
**Autonomous enabled** under **Matching configuration**. Ordinary reviewers cannot
change it, even if granted broad news permissions. Config changes record actor,
time and snapshot. A model/policy mismatch prevents use. Correcting an example
consumed by the active calibration automatically pauses autonomy; an admin must
build/evaluate and explicitly activate a fresh version. New labels alone do not
silently retrain or replace the active version.

With autonomy enabled and supported confidence >=90%:

- A clear match adds an article as duplicate-source information; it does not publish
  a new content version or change severity/remediation.
- A confidently new incident creates an **unreviewed** issue with suggested defaults
  and an inbox notice. An approved baseline is not rewritten.
- Ambiguous, conflicting, stale, incomplete or unsupported cases stay in the inbox.

## Daily Slack digest

Target is fixed to workspace **securityadvisor**, channel
**security-advisor-notifications**. Add a Slack bot to that channel, with `chat:write`,
`channels:read`, and `groups:read` if private-channel discovery is needed. Put its bot
token only in local `.env`/secret configuration, never in Git or chat:

```dotenv
NEWS_SLACK_DIGEST_ENABLED=false
NEWS_SLACK_BOT_TOKEN=
NEWS_PUBLIC_BASE_URL=https://YOUR-APP-ORIGIN
```

Set enabled to true when configured, then recreate `news_notifications`. The token
is passed only to that service, not web/analyzer/matcher. Automatic delivery is off
until explicitly configured. Its worker checks every minute and sends once per local
day at or after **09:00 America/Los_Angeles**, including weekends and DST changes.
An empty scheduled day is recorded as skipped and sends nothing. Late worker startup
catches up once; new items after that day's digest wait for the next day.

The digest contains counts, up to ten brief titles per category, and **app links
only** for new issues, unresolved new review notifications, and automatic duplicate
links. It does not send article excerpts, external source links, or customer data.
Titles use Slack plain-text blocks, and link/media unfurling is disabled. Recipients
must sign into the app and belong to the reviewer group; being in Slack grants no
application access. Use a reachable HTTPS app origin. For a synthetic local Mac
exercise only, DEBUG mode also accepts `http://localhost:8000`; that link resolves
on the reader's own computer and will not work for other reviewers remotely.

Slack's `auth.test` workspace URL and the exact channel name are validated before
posting. Network egress must allow `slack.com`. No Slack message is sent by tests,
installation, migration or an unconfigured worker. You can explicitly test delivery:

```bash
docker compose run --rm news_notifications python manage.py send_news_digest --now
```

A DB outbox prevents concurrent daily sends and records a fixed event window/payload.
Known preflight failures can be explicitly retried with `--now --retry`. If a POST
times out, delivery is **unknown**, not presumed failed. Unknown/in-progress delivery
blocks later sends to avoid blind duplicates. After checking the actual channel,
an operator can reconcile the delivery ID shown in admin:

```bash
# Message is present: mark delivered without another POST.
docker compose run --rm news_notifications python manage.py send_news_digest --resolve-sent DELIVERY_ID
# Confirmed absent: make it retryable, then explicitly --now --retry if still that day.
docker compose run --rm news_notifications python manage.py send_news_digest --confirm-not-sent DELIVERY_ID
```

Slack client message IDs are stable per day, but exactly-once remote delivery cannot
be guaranteed after network failure; reconciliation is intentional. Redirects are
rejected, requests have an overall 60-second subprocess deadline, and remote error
bodies/tokens are not saved. Digest deliveries and embedding attempts are operational
status records; content/feedback/calibration/notification history is immutable.
