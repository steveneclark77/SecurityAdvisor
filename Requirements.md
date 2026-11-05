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
- News source list and access methods, daily schedule/time zone, and framework review interval.
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
- Form edits retain before/after history. Current production data safeguards remain incomplete; only synthetic customers are supported for this milestone. No external email/notification or daily news ingestion is performed yet.


### Draft baseline revision

Unapproved snapshots offer a guided revision page linking to working controls and profile/modifier editing. Capturing a replacement and superseding the old draft is atomic. Preserve both snapshots and record the replacement link, actor, timestamp, and reason. A newer existing snapshot can also be linked as the replacement. Superseded drafts cannot be approved or revised; approved baselines cannot enter this draft-only workflow. Replacement snapshots require their own approval. Revisions capture the current shared working library rather than restoring old content automatically.
