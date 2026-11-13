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

## Inventory explorer (v0.2.1)

Choose a record type in the left sidebar, select a name in the table to preview facts and dependencies, and use the row's **Edit** button to change or archive it. A category has one contextual **Add** action; **All records** has an **Add record** menu. The customer selector is also a compact table.

Search matches names, descriptions, owners, and vendor/products. Apply fact-state and archived filters explicitly. Category counts include active records (or active and archived when selected) before search/state filters; the matching count describes the filtered table. Navigation between types retains these filters. Records are paginated at 50 per page; the preview defaults to the first visible record and never fetches an unrelated/customer-external selection. At narrower widths, the preview stacks below the table and only the table scrolls horizontally.

**Relationships**, **Information to confirm**, and **History** are distinct sidebar destinations. They retain existing editing/archiving/resolution actions and history. Relationships default to active connections; **Show archived** includes archived connections. Connections to archived endpoints remain explicitly labeled. Fact confirmation still does not establish control effectiveness. Historical snapshots retain their original read-only presentation.

Assessment actions, evidence/findings, and contacts adopt the same shared table/preview components in v0.2.2; see [the walkthrough](ENGAGEMENT_WALKTHROUGH.md#shared-record-browsers-v022). The engagement journey remains a workflow. News retains Django admin list/detail conventions. Inventory keeps its type-specific row Edit actions and preview fields while sharing pagination, safe selection, table markup and responsive styles with the other browsers.

## One accountable owner (v0.2.3)

Inventory records and information follow-ups have one optional **Owner** contact and separate **Notes** for supporting people and coordination. Eligible owners are active contacts linked to any engagement for this customer. Engagement investigations, evidence requests and remediation tasks instead use contacts linked to that engagement. Unassigned is valid; a name in Notes is not an owner assignment.

Choose **Add contact** beside the owner dropdown to open the existing contact flow in another tab. For customer inventory, choose which customer engagement will hold the new person's contact role, then save the contact and role link. Return to the original form and choose the **refresh icon** to update its dropdown without losing unsaved fields. Select the new contact explicitly before saving. Contact creation alone does not make an unlinked person eligible.

An existing archived/inactive owner can remain recorded, but cannot be newly assigned. Reassignment choices are active linked contacts. Ownership references protect contacts against deletion. New assessment/report/audit captures store the owner ID and display details; changing a contact's name later does not rewrite captures. Historical JSON remains untouched. There is no previous-owner text field or reconciliation workflow.

## Contextual form help (v0.2.4)

Empty select choices use meaningful labels, such as **Select an operation category**, **Unassigned**, and **No preference**. They retain their existing stored blank values and validation rules. Each editable field has an info icon beside its label; open it to read field guidance in a dialog, then use Close or Escape to return. Checkbox/radio groups share one info control. Required indicators and validation errors remain on the form. Page-level guidance remains visible.

The owner selector has a visible **Add contact** button and a small refresh icon with an accessible **Refresh contacts** name. Complete contact creation and role linking in the new tab, then return, refresh and select the owner. Other unsaved form fields are preserved. The old Add option inside the dropdown and the long owner-guidance panel have been removed.

## Cancel unsaved inventory edits (v0.2.5)

Inventory record, relationship and information-follow-up forms offer **Cancel** beside Save. Cancel navigates back to the customer inventory without submitting, saving, or writing history. Opening a form from the explorer preserves its list category, search, fact-state/archive filters, page and selected preview. Direct form links fall back to the appropriate customer collection. Return destinations are restricted to this customer's inventory path, including for assigned superusers. Cancel also works when required fields are incomplete.

Buttons use the approved light-elevation style: white faces, charcoal text, fine gray borders and soft shadows. Hover, focus, pressed and disabled states share the same stylesheet across consultant, public and admin forms. The button family does not indicate workflow priority.

## Prefill synthetic Harbor Cafe inventory (v0.2.7)

From any customer inventory view, expand **Prefill synthetic Harbor Cafe inventory**, optionally select **Alex Morgan** as **Owner for new records**, and choose **Add missing cafe inventory**. The tool is synthetic-only and requires normal customer assignment, including superusers. Manual entry/editing remains available for targeted testing.

The full template includes 18 records across all seven types:

- Four operations: Orders and payments, Biweekly payroll, Vendor and rent payments, Device maintenance and backup recovery.
- Three provider placeholders: payment processing, payroll and ISP.
- One group of two business laptops.
- Four software examples: hosted POS, QuickBooks Online, Dropbox and an unconfirmed backup service.
- Two networks: business connectivity and guest Wi-Fi.
- One physical-system example: cameras/alarm.
- Three data categories: employee payroll, customer orders/payments and accounting/supplier records. No actual personal, banking or card records are entered.

It also adds 15 directional example relationships and eight open information follow-ups. New facts remain Unknown, criticality Unknown and impact unrated; synthetic provenance distinguishes examples from confirmed customer facts or tested safeguards. Notes and relevant type-specific fields are prefilled. Contact assignment does not grant authorization or certify responsibility.

Existing records are kept by type and normalized name/known aliases, including archived items. Audit markers retain identity after generated records, relationships or questions are edited. Earlier v0.2.6 operation markers remain recognized. Resolved follow-ups are not reopened, and archived objects are not unarchived. Links/questions to archived or ambiguous item matches are skipped; the result message reports added counts and skips. Different kinds sharing a name are not treated as the same record.

The atomic customer-locked service creates only missing records and normal before/after audit entries. Repeating it adds nothing when examples are already present; existing owners, values and historical assessment/report snapshots stay unchanged. A CSRF-protected POST is required. Updates and GET requests do not seed data, and no new migration is needed.

## Sort and filter inventory (v0.2.9)

Click **Name**, **Type / quantity**, **Owner** or **Fact state** to sort; click again to reverse direction. **Action** is not sortable. Quantities sort numerically (2 before 10); names sort alphabetically (Laptop 10 before Laptop 2), using the displayed type/owner/state rather than contact IDs or internal choice codes. Sorting applies to the complete filtered record set before paging, returns to the first page and selects its first visible record. Search/archive/fact-state filters, paging and Edit/Cancel navigation preserve the selected sort. Relationships and information-follow-up tables also offer sortable data headers.

Search, fact-state and archive controls have no info icons. Help remains available on record-entry fields such as owner and notes; explanatory page guidance remains visible.

For tied sort values, Name is always ascending, followed by record ID ascending. Type / quantity sorts by type and numeric quantity in the selected direction before applying those tie-breakers. Sorting Name itself keeps the selected Name direction.
