# SecurityAdvisor Requirements

This document captures requirements agreed during initial planning. It describes intended behavior, not implemented functionality. See [README.md](README.md#planned-versions) for the proposed delivery stages.

## 1. Purpose and scope

- Support a cybersecurity consultant in methodically assessing customer IT infrastructure, online presence, and business dependencies; identifying risks; prioritizing recommendations; and optionally helping implement fixes.
- Initially serve one consultant and US small and midsize businesses across industries. Customers range from novice to expert in IT and security.
- Keep checklists tool-agnostic. Tool integrations or native assessment/remediation capabilities are future possibilities.
- The first-release scope includes profiles, a shared baseline library, intake, manual assessments, evidence, scoring, reporting, remediation tracking, daily news ingestion, periodic framework review, manual approval, feedback history, and reassessment prompts.
- Future versions add optional auto-approval and a team with customer-specific access.

## 2. Intake, profiles, and modifiers

- Customers submit questionnaires through secure, expiring links without accounts or full application access.
- Intake captures business activities, technologies, sensitive data, critical dependencies, and risk-scoring context.
- Recommend a best-fit business profile plus modifiers, explain the recommendation, and allow consultant correction. Exact matches are not required.
- Profiles select controls from a shared library rather than duplicating common guidance.
- Modifiers include payment processing, sensitive health or financial data, software development, public applications, remote workers, operational technology, multiple locations, and government contracts.
- Establish customer-specific material financial-loss thresholds, outage tolerances, critical business periods, and customer dependencies.

### Initial profile catalog

These are the starting profiles; detailed mappings require baseline design and approval.

| # | Profile |
| --- | --- |
| 1 | Software, SaaS, and application development |
| 2 | IT services and managed service providers |
| 3 | Online retail and e-commerce |
| 4 | Physical retail |
| 5 | Restaurants, cafés, and food service |
| 6 | Hotels, lodging, and hospitality |
| 7 | Healthcare practices and clinics |
| 8 | Dental and other outpatient specialty practices |
| 9 | Financial services and insurance |
| 10 | Legal services |
| 11 | Accounting, tax, and bookkeeping |
| 12 | Other professional and consulting services |
| 13 | Real estate and property management |
| 14 | Construction and skilled trades |
| 15 | Manufacturing |
| 16 | Transportation, logistics, and warehousing |
| 17 | Automotive repair and dealerships |
| 18 | Education and childcare |
| 19 | Nonprofits, associations, and religious organizations |
| 20 | Personal services, fitness, and recreation |

## 3. Baseline library

An approved, versioned baseline must exist before news scanning augments checklists. News does not replace foundational security coverage.

| Source | Role |
| --- | --- |
| NIST CSF 2.0 | Organize Govern, Identify, Protect, Detect, Respond, and Recover coverage. |
| CIS Controls v8.1 | Seed actionable safeguards. Begin with IG1; add applicable IG2/IG3 safeguards according to complexity and exposure. |
| CISA Cybersecurity Performance Goals | Cross-check high-impact practices, particularly for smaller businesses. |
| OWASP ASVS and SAMM | Supplement application security and secure development assessments. |
| PCI DSS | Supplement applicable payment assessments. Outsourcing payments does not automatically remove all merchant responsibilities. |
| Sector-specific requirements | Supplement applicable healthcare, financial services, government-contracting, and other obligations identified during intake. |

- Check licensing and reuse terms before incorporating framework text.
- Framework mappings do not imply certification or a legal determination of compliance.
- Universal coverage includes asset inventory, identity/access, devices, patching, email, backups, vendors, data protection, incident response, and recovery.
- Baseline approval requires defined checklist fields and scoring, universal controls, profile/modifier mappings, source references, applicability explanations, and recorded coverage gaps.
- Review frameworks periodically as well as scanning news daily. The framework review interval remains to be selected.

## 4. Checklist and assessment information

Reusable control guidance and customer-specific assessment records together must support all fields below.

| Area | Required information |
| --- | --- |
| Identity | Stable identity, version, profiles/modifiers, applicability criteria, and explanation. |
| Investigation | Tool-agnostic procedure, what to inspect, risk indicators, and evidence to collect. |
| Assessment | Status, findings, evidence, notes, uncertainty, and confidence. |
| Risk | Business and technical explanations, impact dimensions, likelihood rationale, current risk, and priority. |
| Recommendation | Standard remediation, customer-specific actions, estimated cost and effort, and expected residual risk. |
| Implementation | Owner, deadlines, progress, verification procedure, retest evidence, and outcome. |
| Provenance | Framework references, supporting reports, change history, and approvals. |

- Provide explanations suitable for both nontechnical and technical audiences.
- Missing evidence is unknown and creates an investigation task; it must not default to low risk.

### Actionable recommendation structure

- Every control combines a plain-language recommendation summary with ordered, individually identifiable actions.
- Each action includes concrete tool-agnostic instructions, applicability/prerequisites and exceptions or alternatives, and verifiable evidence or a safe completion test.
- Explain risk reduction without promising complete prevention. Distinguish separate mechanisms such as phishing-resistant MFA and managed-device restrictions.
- Control rationale and sources support actions; optional action-level references can link vendor-specific implementation guides.
- Preserve actions in baseline snapshots. Existing historical snapshots without actions remain readable and must not be silently augmented.
- Future assessments track actions individually without requiring separate risk scores for each action. Completion tracking is not implemented in the current library milestone.
- Split broad controls when different owners, evidence, or remediation make separate assessment useful; length alone is not a reason to split.

## 5. Scoring and priority

Use separate five-level business impact and likelihood ratings. A documented matrix determines priority; the exact matrix and priority labels remain to be approved.

### Business impact

Impact means expected consequences if the risk materializes: financial loss and recovery costs, interruption of critical operations, and reputational harm affecting retention or acquisition. Capture legal, contractual, privacy, and safety consequences where applicable.

Thresholds are customer-specific. Keep individual dimensions visible; severe consequences must not disappear through averaging. The exact aggregation rule remains open.

| Level | Definition |
| --- | --- |
| 1 | Minimal disruption or loss; routine recovery. |
| 2 | Limited loss or disruption, manageable through normal operations. |
| 3 | Material loss, operational interruption, or customer harm. |
| 4 | Major interruption, financial loss, or lasting reputational harm. |
| 5 | Threatens business viability or causes severe, prolonged consequences. |

### Likelihood

Likelihood means how plausible exploitation is for this customer, considering exposure, exploit prerequisites and ease, available exploit methods, active/recent exploitation elsewhere, and existing safeguards.

| Level | Definition |
| --- | --- |
| 1 | Exploitation requires exceptional conditions; exposure is tightly constrained. |
| 2 | Exploitation is difficult or requires substantial access or prerequisites. |
| 3 | A credible exploit path exists with achievable prerequisites. |
| 4 | Exploitation is practical, exposure is significant, or applicable attacks are occurring. |
| 5 | Applicable exploitation is widespread, or evidence indicates attempts against the customer. |

- Attacks elsewhere raise likelihood when applicable to the customer's technology and circumstances.
- Lack of recent news does not by itself lower likelihood.
- Record confidence separately from ratings.
- Findings retain current risk, recommended actions, and expected residual risk.

## 6. News ingestion and approval

- The consultant supplies the source list. Scan configured sources daily after baseline approval.
- Assess each discovered item for relevance, applicable profiles and technologies, and overlap with existing checklist items.
- Propose **update** for new information about an existing item, **add** for a significantly different risk, or **ignore** when no checklist change is warranted.
- Record every discovered item in a data table with its source link, proposed and final dispositions, affected controls where applicable, and a brief explanation. Retain supporting source evidence.
- Group duplicates or related reports while preserving individual source links.
- News records and checklist changes are separate: several reports can support one change, and one report can affect several controls/profiles.
- Initially require consultant approval of every disposition, including ignores. Proposals must not change the approved library before approval.
- Preserve approvals, rejections, edits, and reasons as feedback. Allow review and correction of ignore decisions.

The motivating example concerned plugins being installed into coding agents, illustrating a software-specific exposure. Its contents have not been verified for this document:

<https://archive.codenewsletter.ai/2117731409246978489>

### Feedback and later automation

- Use decision history to improve future classification and proposals.
- Version classification rule/model changes and evaluate them against historical decisions before activation.
- Do not silently activate new classification behavior through learning.
- Provide optional auto-approval in a later version, disabled initially and explicitly enabled by the consultant.
- Auto-approval eligibility, evaluation metrics, and activation thresholds remain to be designed.

## 7. Versioning and reassessment

- Version baseline controls and approved library changes.
- Each assessment/report retains the checklist version used. Library updates must not silently rewrite historical findings or reports.
- Approved changes flag affected customers and offer reassessment tasks.
- Preserve traceability between sources, proposals, decisions, control versions, and customer findings.

## 8. Reports and remediation

- Produce executive summaries, detailed technical findings, and prioritized remediation plans.
- Explain business consequences and actions for the customer's level of understanding.
- Track implementation assignments, deadlines, and progress.
- Support verification and retesting with evidence and outcomes.
- Keep expected residual risk distinct from verified results.
- Report templates and export formats remain to be selected.

## 9. Sensitive data and access

- Assume customer records, evidence, and notes are sensitive.
- Enforce customer separation from the outset, including evidence and reports.
- Support evidence files and notes; exclude storage of passwords, API keys, and other authentication secrets from the first release.
- Intake access must be limited to the intended questionnaire and must not expose assessments or other customers.
- Future team members may access only assigned customers.
- Retain decision/change history sufficient to explain assessment and library outcomes.
- Retain customer data for three years. There is no additional data-location requirement; expected operations are US-only. The retention clock start, backup treatment, and deletion exceptions remain to be defined; engagement closure is a proposed default only.
- Resolve authentication/MFA, encryption, retention/deletion, backups, file handling, and operational audit details during technical design before accepting sensitive production data.

## 10. Acceptance criteria

The complete first release must demonstrate that:

1. An approved baseline exists before news can augment it.
2. Intake recommends profiles/modifiers with reasons and permits consultant correction.
3. Assessments record applicable controls, evidence, unknowns, findings, scores, and recommendations.
4. Assessments support reporting, implementation tracking, and retesting.
5. Daily ingestion retains source records and traceable add/update/ignore proposals, including duplicate grouping.
6. Initial approval mode prevents any proposed disposition from changing the library without approval.
7. Approved changes preserve history and flag affected customers for reassessment.
8. Intake and customer data access cannot expose another customer's information.

## 11. Open design decisions

- Hosting provider, production file storage, and deployment. The selected application stack is Django/Python with PostgreSQL, server-rendered templates, and Docker Compose; initial operation is local on Windows 10 through WSL2. HTMX/Bootstrap can be added as needed.
- Detailed intake questions, control content, mappings, and baseline review procedure.
- Priority matrix, impact aggregation, confidence scale, and exceptional-priority handling.
- Additional news sources/access methods and the framework review interval. Initial RSS/Atom sources and a 24-hour worker schedule are selected in v0.1.9.
- Relevance, novelty, duplicate, and affected-customer matching rules.
- Classification approach, feedback application, evaluation, and auto-approval safeguards.
- Report exports, templates, and notifications.
- Security and data lifecycle details identified in Section 9.

Resolve these decisions before implementing their relevant milestones. Technology decisions recorded above are selected; hosting and production operations remain open.


## 12. Customer workflow implementation decisions

- Engagements record scope, assessment authorization, separate change authorization, exclusions, contacts, deliverables, customer-specific impact context, and review dates/triggers.
- Customer workflow access requires an explicit customer assignment, even for staff/superusers. Global library administration does not expose customer models. Team-assignment management remains future work.
- Intake/evidence invitations are purpose-scoped, seven-day, revocable bearer links with hashed stored tokens and single final submission. Intake supports draft progress. Development intake recommendations are provisional business-activity/modifier mappings, not an AI classification.
- Assessment actions capture the approved baseline's instructions and mappings. Applicability, implementation, verification, and confidence are separate; exclusions require rationale and cannot be marked tested.
- Evidence requests can be generated per control without duplication; evidence can be reused across actions and findings within the same engagement. Attachments are private downloads with generated filenames, a 5 MB limit, and restricted types/basic content checks. Production malware scanning remains outstanding.
- Findings may group several action gaps; both ratings are required for a priority other than unrated. Priority is consultant judgment until an automatic matrix is approved. Accepted risk requires a decision-maker/rationale and review date.
- Remediation separates planned, in-progress, implemented/unverified, partial, verified, and reopened states. Change authorization and verified dependencies gate implementation. Passing evidence-backed retests establish verification; later failures reopen tasks.
- Reports preserve executive and technical views, evidence provenance, unknowns, exclusions, and baseline coverage gaps. Browser printing/PDF is supported; dedicated document export is not yet implemented.
- Approved relevant library changes create review tasks, not automatic customer finding updates. Matching is conservatively based on captured profile/modifiers and requires consultant confirmation.
- Form edits retain before/after history. Current production data safeguards remain incomplete; only synthetic customers are supported for this milestone. No external email/notification is performed. Daily RSS/Atom news collection and manual review are implemented; AI classification remains planned.


### Draft baseline revision

Unapproved snapshots offer a guided revision page linking to working controls and profile/modifier editing. Capturing a replacement and superseding the old draft is atomic. Preserve both snapshots and record the replacement link, actor, timestamp, and reason. A newer existing snapshot can also be linked as the replacement. Superseded drafts cannot be approved or revised; approved baselines cannot enter this draft-only workflow. Replacement snapshots require their own approval. Revisions capture the current shared working library rather than restoring old content automatically.


### Running application version

Display the running application version in the header, sourced from the repository-root `VERSION` file. Use SemVer `major.minor.patch`. Each user-requested change increments the patch unless the user specifies otherwise. Version-file updates take effect when the application restarts/rebuilds.


### Required-input interaction

Disable action buttons until their form inputs are complete and valid; retain server-side validation. Baseline approval requires a rationale and one checkbox, “I have reviewed the baseline.” An accessible info button opens a dialog listing the existing coverage, applicability, sources, and certification-limit checks. The dialog is informational; the checkbox is mandatory.


### Reusable engagement contacts

- Engagement creation omits the old contact field and opens a contact-selection/creation step. Engagements can be saved without contacts, but need at least one active, non-archived linked contact before starting an assessment.
- Contacts are independent records with first name, last name, default title, organization, office/cell phones, email, preferred method, and archive status. Require first/last names and at least one contact method. Phone fields support international formats/extensions. Single-name support is a future consideration.
- A contact can link to zero or more engagements. Each engagement-contact link has one or more roles, optional title/affiliation overrides, active status, and a primary designation. Only one active primary is allowed per engagement.
- Contacts do not create accounts, authorize assessments/changes, or grant access. Shared edits/archiving require explicit contact-management access and a confirmation when used by multiple engagements. Engagement members may read linked contacts and edit only their local link metadata, without learning other customer relationships.
- Existing-contact reuse requires explicit management access; duplicate checks search only accessible contacts, warn, and never auto-merge. No universal email uniqueness constraint is imposed.
- Deactivation unlinks while retaining history. Archive instead of deleting historical people. Preserve original free-text contacts as legacy notes requiring review. Reports capture contact details at report time.
- Evidence/task ownership and authorization references remain unchanged in this milestone; structured references and historical assignment snapshots will be connected in a later change.


### Visual hierarchy and actions

Explanatory-only blocks must be visually distinct from data/control sections using a labeled guidance panel. Contacts with no reusable records show linking guidance, while available records offer explicit Link contact actions. Creation, editing, linking, continuation, downloads, and other workflow actions use consistent button styling; safe navigation links to forms retain link semantics, and state changes remain POST-only. Navigation and source references remain recognizable links.


### Automated form and CSRF regression coverage

Every application POST route must have a valid-submission payload and persisted-outcome assertion in the shared test inventory. Verify legitimate HTTP Origin and HTTPS Referer submissions as well as rejection of missing/incorrect tokens and null/foreign origins. New POST routes must fail the coverage guard until added. Real-browser CI runs Chromium and WebKit over intake draft/save/reload/finalization, public evidence upload, authenticated application forms, and representative admin forms. Test token rotation/reload recovery and invitation referrer privacy without disabling CSRF or injecting browser headers. Use only synthetic fixtures, temporary evidence storage, and isolated test databases. Missing browser tooling fails its job rather than skipping verification.


### Customer inventory and operational dependencies

- Maintain a customer-level inventory shared across engagements: business operations, outsourced providers, devices/countable equipment groups, software/cloud applications, networks/ISP, physical/operational security systems, and data sets.
- Capture owners, source/provenance, unknown/reported/confirmed state, review dates, support/configuration, access paths, data-handling responsibilities, and explicit exposures. Reported facts require provenance; confirmed facts require a review date and do not imply a passed control.
- Customer-facing, back-office, and infrastructure/KTLO operations use the same criticality and impact model with no category-based priority advantage. Capture recurring schedules, deadlines/time zones, critical windows, outage/data-loss tolerances, workarounds, and financial/availability/reputation/privacy/safety/contractual consequences per operation.
- Connect same-customer records directionally to show dependencies, providers, data handling/transfers, access paths, networks, and safeguards. Reject self-links and cross-customer endpoints; preserve archived records and history.
- Treat payroll/benefits, vendor and rent payments, accounting/banking, identity operations, patching, backups, monitoring, and connectivity as first-class assessment scope alongside orders/payments and customer data. Distinguish employee PII and uncertain payment-data storage from verified facts.
- Intake Information to confirm captures missing environment facts and creates idempotent customer-level follow-ups on final submission. Preserve the legacy unknowns JSON key and saved drafts. Existing intakes can explicitly generate follow-ups without duplicates or overwriting resolutions. Free text is not automatically treated as verified inventory.
- Explicit inventory exposures offer modifier suggestions for consultant review, without silently changing approved baselines or evaluating safeguards.
- Capture immutable inventory facts when starting an assessment. Findings may link only to records captured for that assessment/customer. Reports preserve both assessment-time inventory and separately labeled report-time inventory. Legacy assessments remain explicitly uncaptured, never backfilled from current facts.
- Enforce assigned-customer access for every inventory view and relationship, including superusers. Use synthetic data only until production data safeguards are complete; no credentials or sensitive record contents belong in the inventory.

### Initial news collection implementation (v0.1.9)

Daily RSS/Atom ingestion stores all feed articles as unverified candidates, deduplicated per source URL. Sources are configurable database records. Severity, type, identifiers, and remediation require consultant judgment. Append-only add/update/ignore reviews preserve actor, rationale, proposed guidance, related controls, duplicate links, and issue snapshots. No automatic library changes occur. AI relevance analysis, proposal generation, and automatic application remain future work. See docs/NEWS.md for supported boundaries.

### Issue version history and provenance (v0.1.10)

Issue identity is separate from immutable full-content versions. Each meaningful edit creates a sequential successor with actor, time, origin, and required change reason. Supporting sources are per-version references, including captured attribution and exact publication links; consultant authorship and supporting publishers are separate. Stale writes are rejected. Reviews select the exact current version and later versions require fresh review. Legacy content becomes version 1; old review snapshots remain untouched without inferred version attribution. Publisher changes produce unverified proposal versions without overwriting consultant severity/remediation, and normal sightings create no version. Database guards protect history and current-version transitions. Downgrading by flattening history is unsupported.

### Source URL identity (v0.1.11)

The canonical website URL is the Source primary key and duplicate websites are rejected. Names are non-unique labels; mutable feed endpoints are separate from permanent website identity. Preserve source relationships, immutable reference snapshots, legacy numeric identifiers, and old audit/review JSON during migration. Stop for duplicate canonical websites instead of silently merging historical issues. Seed CISA, UpGuard, Schneier on Security, and SecurityWeek by URL without overwriting existing configuration.

### Automatic news scan configuration (v0.1.12)

Global automatic news scanning requires explicit deployment opt-in through `NEWS_AUTO_SCAN_ENABLED=true`; it defaults off. While off, loop mode remains idle without database/feed access. The setting persists across updates and applies after worker recreation. Manual one-shot scans remain available, with approved-baseline and enabled-source checks.

### Feed fetch deadline (v0.1.13)

Each feed fetch has an overall 30-second parent-enforced deadline covering DNS, redirects, connection/TLS setup, headers, and body reads. Fetching uses a network-only subprocess that is killed and reaped on timeout. A timeout becomes a retained failed scan, and later sources continue. Public-IP pinning, hostname TLS verification, response/parser limits, storage quotas, and the automatic-scanning default-off setting remain enforced.

### Guided engagement UI (v0.2.0)

Use a grouped journey rail with factual work-status text and shape markers, explicit suggested-next guidance, and small downward connectors. Keep one rail action per work area; use Start for untouched work, Edit for started work, and Review for preserved intake. Display only the selected record workspace alongside the rail, retaining existing editing, evidence, finding, remediation, report, and history workflows. Preparation bullets are informational. Recommendation and status derivation is read-only, scoped to the assigned customer/engagement, and does not imply verification or enforce an order. Preserve existing authorization and validation gates. Use shared styles/components and responsive layouts.
