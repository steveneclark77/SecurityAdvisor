# SecurityAdvisor

SecurityAdvisor is a planned application for cybersecurity consultants who assess a company's IT infrastructure, online presence, and business dependencies; identify security risks; and help customers prioritize and implement improvements.

## Why it is valuable

A software company, Shopify retailer, restaurant, and auto repair shop have different exposures while sharing foundational security needs. SecurityAdvisor will turn a shared control library into practical, customer-specific assessment checklists. It will help consultants work consistently, explain risks to novice and expert audiences, prioritize action by business consequences, and maintain guidance as threats change.

## How it will be used

1. A customer completes intake through a secure, expiring link without creating an account.
2. The application recommends a best-fit business profile and relevant modifiers; the consultant reviews and corrects them.
3. The consultant follows a tool-agnostic checklist, collects evidence, and records findings and uncertainty.
4. Findings receive separate five-level business impact and likelihood ratings using customer-specific thresholds.
5. The consultant produces executive and technical reports and a prioritized remediation plan, tracks implementation, and retests fixes.
6. Daily news ingestion and periodic framework reviews propose library changes. Initially, the consultant approves every add, update, and ignore decision.
7. Approved changes flag affected customers for reassessment while preserving historical assessments and reports.

An approved, versioned baseline must precede news augmentation. NIST CSF 2.0 organizes coverage, CIS Controls v8.1 seeds actionable safeguards, and CISA Cybersecurity Performance Goals provide a coverage check. OWASP, PCI DSS, and sector requirements supplement applicable assessments. Source reuse terms must be checked before incorporating framework text.

The initial full user is one consultant. Customer data separation is required from the outset, supporting future team access limited to assigned customers. Evidence files and notes are supported; storing authentication secrets is excluded from the first release.

## Planned versions

These are proposed delivery stages, not released capabilities or delivery commitments.

| Version | Planned features |
| --- | --- |
| **0.1 — Baseline design** | Shared control model, intake and scoring definitions, approximately 20 business profiles and modifiers, framework mappings, and approval of the initial baseline. |
| **0.2 — Assessments** | Consultant access, customer separation, expiring intake links, profile recommendations, manual assessments, evidence, findings, and risk prioritization. |
| **0.3 — Reports and remediation** | Executive summaries, technical findings, prioritized plans, task ownership and deadlines, implementation tracking, verification, and retesting. |
| **1.0 — Maintained library** | Daily news ingestion, periodic framework review, add/update/ignore proposals, mandatory manual approval, decision history, feedback capture, and reassessment prompts. Completes the agreed first-release scope. |
| **1.1 — Controlled automation** | Versioned classification improvements evaluated against historical decisions and optional, explicitly enabled auto-approval. |
| **2.0 — Team collaboration** | Multiple consultant users with access restricted by customer assignment. |
| **Future exploration** | Assessment/remediation tool integrations or native capabilities; scope and timing remain undecided. |

## Current status

The baseline library includes 20 profiles, eight modifiers, and 14 draft controls with ordered, applicable, verifiable actions. Captured baselines require explicit review and approval. Unapproved drafts have a guided revision flow that captures a replacement, marks the old draft superseded, and preserves both snapshots.

The customer workflow now supports assigned synthetic customers, scoped engagements and business context, expiring intake/evidence links, assessments pinned to approved baselines, action-level observations and reusable evidence, findings with documented risk judgments, authorized remediation plans and dependencies, retesting, preserved executive/technical reports, edit history, and affected-customer review after approved library changes.

Start with [the synthetic engagement walkthrough](docs/ENGAGEMENT_WALKTHROUGH.md). No exercise customer or approved baseline is automatically created. Starter guidance is incomplete; this is not a certification tool. Use synthetic data only: production MFA, encryption/backup operations, malware scanning, and retention automation remain unfinished. Daily news ingestion, automatic scoring/approval, and team-assignment management are still planned. Reports can be printed or saved as PDF through the browser.

## Development

The application uses Django 5.2 LTS and PostgreSQL, with Docker Compose for local development. It uses server-rendered templates and local CSS; HTMX/Bootstrap can be introduced when needed. Python dependencies are pinned in `requirements.txt`. SQLite is available as an explicit development/test fallback.

See [the setup guide](docs/SETUP.md) for Windows 10/WSL2 prerequisites, startup, baseline review, tests, and production limitations. See [Requirements.md](Requirements.md) for detailed product requirements.
