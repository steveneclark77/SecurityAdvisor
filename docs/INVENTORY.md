# Customer inventory and keep-the-lights-on operations

Open **Inventory** in the header, or **Customer inventory and operations** on an engagement. Inventory belongs to the customer and is shared across that customer's engagements. Access requires customer assignment, including for superusers; it is not exposed through global admin.

## Build the map progressively

1. Add business operations: taking orders, accepting payments, biweekly payroll, monthly vendor/rent payments, and infrastructure duties such as identity administration, patching, backups, monitoring, and connectivity recovery.
2. For each operation, record its owner, frequency/deadline and time zone, critical windows, tolerated interruption/data loss, workarounds, and financial/availability/reputation/other consequences. Optional impact ratings use the same 1–5 scale. There is no automatic priority advantage for customer-facing work over back-office or KTLO work. Criticality requires a business rationale; unknown is not low impact.
3. Add providers, devices or counted equipment groups, software/cloud applications, networks/ISPs, physical security/operational systems, and data sets. Fields adapt to the selected record type. You can record a placeholder provider with unknown facts rather than invent its name.
4. Record product/vendor, location, support status, security configuration, sign-in/access paths, and data-handling responsibilities where relevant. Device groups include quantity and operating system. Capture antivirus, local/network firewall, encryption and management arrangements; ISP-bundled safeguards; physical security remote access; and important software such as QuickBooks or Dropbox.
5. Connect the records with directional relationships and describe the access or exchange method. Examples: payroll **depends on** payroll provider; provider **stores/handles** employee PII; accounting **transfers data to** banking; backup maintenance **uses** backup service; cameras **connected to** network; router **protects** business devices.
6. Mark facts unknown, customer-reported, or consultant-confirmed. Reported facts require provenance; confirmed facts also require a review date. Confirmation means the inventory fact was checked, not that its security safeguard passed.
7. Track missing facts in **Information to confirm**, with an owner, due date, related item, and eventual response. Use Edit / resolve follow-up to close it with an explanation.

Never store passwords, tokens, recovery keys, employee records, or actual card details. Describe information categories and handling. Quick reorder does not establish that a merchant stores card numbers: explicitly distinguish unknown storage, full card data, masked references, and provider tokens, then investigate responsibilities.

## Intake and existing records

The public intake still allows a broad environment description. **Information to confirm** replaces the label Unknowns and prompts for provider names, software/features, device configurations, network/ISP services, and administrators/connections. Safeguard-effectiveness questions belong to assessment actions.

The underlying `unknowns` JSON key is preserved so existing draft/submitted answers survive the change. Final intake submissions create one open inventory follow-up from this text. Existing submitted intakes can be brought into the queue with **Create inventory follow-ups from intake** on the engagement page. Repeating this does not duplicate requests, overwrite edited questions, or reopen resolved requests. Save progress alone does not create inventory records/follow-ups.

Free text is not automatically parsed into confirmed assets, providers, or dependencies. The consultant enters and verifies the map. Explicit exposure flags suggest reviewing matching assessment modifiers; suggestions do not silently change baseline approvals or select modifiers for the consultant. Names and categories do not by themselves establish whether a control passed.

## Assessments, findings, and reports

New assessments capture all retained inventory records, connections, and information gaps at creation, with a timestamp. Archived records remain labeled for historical context. Review active operation scope and modifier suggestions before starting. No new baseline approval is created by entering inventory.

Finding forms can link to inventory records that belong to the selected assessment's captured inventory and this customer. Newly entered records require a new assessment to be represented as assessment-time facts. Existing free-text affected-assets notes remain supported.

Reports preserve both the inventory used by each assessment and a separately labeled current inventory at report generation. Later inventory edits or archiving do not rewrite historical assessments/reports. Assessments made before this feature say their inventory was not captured; they are not backfilled from today's facts. Existing findings and approvals are preserved.

Inventory form edits are recorded as before/after history. Archive rather than delete records; connected records and audit history are retained. Relationships may represent genuine circular dependencies; only self-links and cross-customer links are rejected.

## Harbor Cafe exercise

Use fictional records only. Start with three operations:

- Orders/payments: customer-facing, material interruption after 30 minutes during service.
- Payroll: back-office, biweekly, with elevated impact near the submission cutoff; employee PII involved.
- Vendor/rent payments: back-office, monthly deadlines, with invoice-fraud and banking/accounting dependencies.

Add a KTLO operation for device maintenance and backup recovery. Give each its own owner, deadlines, impact, and workaround; do not assume the service-hours tolerance also fits payroll or rent.

Create unknown-provider follow-ups, two grouped laptops with configuration unknowns, accounting/file-sharing applications, the ISP/network, and physical security if relevant. Connect them with the operation and data records. Then start an assessment to freeze those facts for the exercise.
