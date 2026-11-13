# Running a synthetic customer engagement

This walkthrough is for a consultant-led exercise, not a completed assessment. Do not use real customer data yet. No customer, baseline approval, finding, or remediation result is automatically created by installation or update.

## 1. Prepare the application and library

Apply the update with `./update.command` on macOS, or follow the manual rebuild/migration commands in SETUP.md. Sign in using your consultant account and open **Customer engagements** from the top navigation.

Before creating an assessment, use **Library** to review starter controls and capture a baseline. Record the incomplete framework mappings and any missing coverage. Use the info icon beside “I have reviewed the baseline” to review the coverage, applicability, references, and limitations checklist. Enter the rationale and select the required checkbox to enable approval. An approval for a synthetic exercise is not a compliance claim or evidence of complete coverage.

If changes are needed before approval, choose **Revise this draft**, edit and save the working guidance in the linked admin pages, then return and capture a uniquely named replacement. The original becomes **Superseded** and links to the replacement; review and approve the replacement separately. The revision captures the current shared working library and does not silently restore the old snapshot.

## 2. Create the customer and scope

Choose **Create synthetic customer**, name it **Synthetic Harbor Cafe**, and confirm that the records contain no real information. The creating user is assigned to that customer; other staff users do not automatically receive access, including superusers through customer workflow screens. No customer models are exposed through the global admin.

Create an engagement such as **Initial security improvement exercise**:

- Scope: fictional email administration, hosted ordering, payment administration, and business laptops.
- Exclusions: intrusive scanning, live payment processing, and changes to real services.
- Assessment authorization: fictional owner authorized interviews, synthetic configuration review, and safe test-account demonstrations.
- Change authorization: initially leave blank. Assessment permission does not authorize remediation.
- Deliverables: executive summary, technical findings, and a prioritized plan.
- Business context: describe the cafe's critical operations, outage tolerance, reputation concerns, and financial impact thresholds. Record unknown thresholds explicitly rather than inventing certainty.
- Follow-up: choose a review date and triggers such as a provider change, new location, or relevant incident.

Saving the engagement opens a second screen, **Contacts for the engagement**. Create **Alex Morgan**, title **Owner**, organization **Synthetic Harbor Cafe**, email **alex@example.test** (fictional), and optionally synthetic office/cell numbers. At least one contact method is required. Save the person, then assign the **Business owner** role and mark Primary/Active. Continue to the engagement once an active contact is linked.

Add additional people by creating contacts or selecting existing contacts you have permission to manage. A contact can exist with no engagement or be reused across engagements; roles and title/affiliation overrides apply only to the link. Use **Manage contacts** any time to change roles, choose a primary, or deactivate a link. Edit/archiving shared person details requires explicit contact-management access and confirmation when shared. The application does not grant logins or authorization by linking a contact.

Existing free-text contacts appear as legacy notes requiring review; create structured records manually rather than assuming the text was parsed. Evidence/task owners and authorization references remain separate and are not silently converted to contact links.

Three-year retention is a requirement, not automated deletion. Its starting event, backup treatment, and exceptions remain undecided.

## 3. Exercise intake

Create an expiring intake link. The application shows a relative path once; copy it or open it locally to role-play the customer. The link lasts seven days, is scoped to intake, and is consumed after final submission. Save progress before final submission to test resuming.

Choose restaurants/food service, payment processing, and any other exposures relevant to the fictional business. Describe services and business consequences, using the unknowns field for unresolved questions.

Return to the engagement page to review the provisional profile recommendation. It uses the customer's selected business activity and exposures, not an AI determination. A mixed or unknown industry produces an explicitly provisional fallback. Intake does not overwrite the consultant's business context.

External customers cannot reach a laptop-only deployment. Do not expose the development server to the internet to test intake.

## 4. Build inventory, then start and review an assessment

Before starting, open **Customer inventory and operations** and follow [the inventory guide](INVENTORY.md). Include payroll, vendor/rent payments, and infrastructure/KTLO operations alongside orders/payments. Record providers, devices/software, data, and connections; keep missing facts in **Information to confirm**. New assessments capture these facts, so fill them before starting rather than retroactively substituting current information.

Choose **Start assessment**. Select an approved baseline, confirm the best-fit profile and modifiers, and explain any overrides. Choices must exist in the selected baseline snapshot.

The assessment creates one result per captured action. Universal/profile/modifier matches start as applicable; other controls start excluded with an explanation that must be reviewed. Excluded actions are not verified safeguards. Legacy baselines without detailed actions produce an explicit manual-investigation placeholder.

Use the applicability filters to review exclusions and unknowns. Every action starts with unknown implementation and no verification. Working-library edits do not alter these captured instructions.

## 5. Request and record evidence

Choose **Generate evidence requests for this checklist** to create one request per non-excluded control. Repeating this operation preserves existing requests and consultant edits. Set owners and due dates through **Review request**.

For a synthetic PR-01 investigation, request a fictional/redacted identity-policy export and recovery procedure. Either record evidence directly or create a scoped evidence-submission link. Submission links expose only that request's instructions, not findings or other customer records. Received requests require consultant review.

Evidence records include provenance, collection date, notes, and an optional attachment. Allowed attachments are UTF-8 text, PDF, PNG, and JPEG, up to 5 MB with basic content/type checks. Files have generated names, reside outside public web paths, and require assigned consultant access to download. These checks are not malware scanning or production security certification. Never upload credentials or real customer information.

One evidence record can support multiple actions and findings.

## 6. Investigate an action and draft a finding

Open a PR-01 action and choose **Investigate and record result**. In the fictional scenario, suppose a privileged account can use a weak sign-in method:

- Applicability: applicable, with a reason.
- Implementation: partial.
- Verification: failed only if a synthetic test/evidence actually demonstrates the failure; otherwise not tested or inconclusive.
- Confidence: explain uncertainty in observations.
- Evidence: link the fixture, enter its date, and describe the procedure and result.

Verification requires linked evidence, dated observations, and records the consultant and timestamp. Unknown results remain investigation work.

Choose **Draft finding from this action**. Review the prefilled condition, risk, recommendation, action links, and evidence. Add affected assets, separate financial/availability/reputation consequences, likelihood rationale, limitations, and expected residual risk.

Use five-level impact and likelihood ratings. Priority is explicitly documented consultant judgment: no automatic matrix or impact aggregation has been approved. Missing ratings require an unrated priority. Accepted risk requires a named decision-maker and rationale in the acceptance text plus a review date.

Do not create one finding for every failed checkbox automatically. Group related actions when they represent one business risk; separate findings when owners, consequences, or remediation differ.

## 7. Plan and authorize improvements

From the finding choose **Plan remediation**. Refine the suggested instructions and verification procedure. Assign an owner, due date, cost/effort estimates, dependencies, temporary safeguards, and recovery arrangements.

Keep the task planned until separate change authorization is recorded. The application requires task-specific authorization for implementation and prevents progress past unverified dependencies. Dependency cycles are rejected.

Marking a task implemented means verification is pending. It does not mean the finding has been resolved.

## 8. Retest and inspect history

After the fictional change, choose **Record retest**. State the procedure, tester date, outcome, linked evidence, and residual risk. A passing retest marks the task verified; a failure reopens it; partial and inconclusive results remain distinct. A newer failure cannot be overridden merely because an older test passed.

Use a safe synthetic demonstration such as denying a weaker sign-in method while confirming an approved recovery path. Do not test real customer systems without authorization.

The engagement history records before/after values for form edits. Retest records are additive. Expected residual risk in a finding and observed residual risk after testing remain separate.

## 9. Produce and compare reports

Choose **Capture executive and technical report**. The report contains:

- Scope, exclusions, business context, assessment authority, and baseline versions/coverage gaps.
- Prioritized findings with business consequences, rationale, and recommendations.
- Owners, due dates, dependencies, authorization, verification steps, and retest outcomes.
- Action results, unknowns, exclusions, evidence provenance, and limitations.

Use the browser's Print / Save as PDF feature for an artifact. The report print button expands investigation details before opening the print dialog. Reports without findings explicitly do not imply security assurance.

Generate a report before and after remediation to confirm that the earlier snapshot remains unchanged. Printing and browser-generated PDFs are available; dedicated DOCX/PDF export templates are not yet implemented.

## 10. Test ongoing review

Edit a working control, capture a new baseline, and explicitly approve it. Relevant changed/new/removed controls create affected-customer review entries based on captured profiles/modifiers. They do not silently update existing assessments or imply confirmed product exposure.

Open the review queue to plan a dated reassessment or dismiss it with a rationale. Start a new assessment from the newer baseline if needed. Daily RSS/Atom news collection and manual candidate review are available in admin; see [NEWS.md](NEWS.md). AI relevance classification remains planned. News reviews do not change guidance automatically; explicitly approved library changes exercise the reassessment path.

## Feedback to capture during the exercise

Record confusing questions, missing evidence examples, awkward navigation, excessive repeated entry, unclear risk definitions, grouping problems, and report omissions. Distinguish a workflow problem from a scenario where the underlying facts are simply unknown. We will refine the application after this exercise.

## Engagement journey (v0.2.0)

The engagement overview groups work into **Understand the business**, **Assess and investigate**, and **Improve and report**. Read the status text and counts beside each node; the filled, half-filled, and hollow circles also distinguish recorded work, open work, and areas without records. These describe stored work, not security verification or complete coverage.

Use the single **Edit**, **Review**, or **Start** action beside a step. The rail opens the relevant work area or existing form. Record collections, original intake, evidence requests, findings, remediation/retests, and reports appear in the right-hand pane when selected. Scope/context and contacts have their existing editing actions there. Inventory opens the shared customer inventory, and a first assessment opens its existing form. Started assessments open their record list, including **Start another assessment**. Engagement history and submission-link revocation are available below the rail.

**Suggested next** is read-only guidance, with an explanation and preparation bullets. It does not lock navigation or indicate that a button is authorized or ready to submit. Existing server-side baseline/contact/change-authorization rules still apply. Reports and other areas remain reachable before earlier work is finished. The recommendation proceeds from contacts/context and optional intake through inventory, assessment, evidence, remediation when findings warrant it, and reporting; active work can send it back to investigation or retesting. Unknown inventory facts do not prevent assessment guidance once inventory records exist.

There is no separate completion checkbox or automatic intake-review-completed flag. Submitted intake is labeled **Recorded** and uses **Review**; it does not claim consultant review is complete. Inventory with unknown facts or open follow-ups remains **In progress**. Assessment status reflects applicable actions still unknown, untested, or inconclusive. Pending evidence requests and unverified remediation remain open work. A failed assessment test may still be a recorded result, and no stage status implies the customer is secure. Existing captures and audit records are preserved.

In the inventory explorer, choose **Operations**, then the contextual **Add business operation** action. Add the Harbor Cafe operations before selecting Providers, Devices, and the remaining types. Select a record name to preview its facts and dependencies; use **Edit** in its row to change it. Use the sidebar's **Relationships** to connect records and **Information to confirm** to manage unknowns. Search/state/archive filters affect the table, not historical assessment snapshots.

## Shared record browsers (v0.2.2)

Assessment actions now use search, applicability/verification filters, and a compact table. Select an action name to preview its frozen instructions, recommendation, verification procedure, recorded observations, owner and status. **Investigate and record result** and **Draft finding from this action** appear once, in the selected preview. Evidence-request generation remains an explicit CSRF-protected submission above the list; filtering does not generate records.

The engagement's evidence work area separates **Evidence requests**, **Evidence register**, and **Findings**. Each collection has one creation action and its own table/preview. Requests have status filters and the selected request's existing review/submission-link actions. Evidence previews retain provenance, collection date, notes and private attachment download. Findings have priority filters and retain impact/likelihood, confidence, recommendations, limitations and risk acceptance; expanded technical details remain available. Counts describe each complete collection before filtering, rather than asserting completeness or security assurance.

The contact directory and engagement contacts share searchable tables and person previews. Search supports full names, organizations, email and titles. **Linked contacts** preserves active/inactive links and archived people, with a visibility filter. **Available to link** contains only active people you explicitly manage who are not already linked; a deactivated existing link must be reactivated through its retained link record. Role/primary/unlink edits and shared-person edits remain separate actions and permissions. Shared-person edits still require the existing confirmation when applicable. Seeing a contact through an assigned engagement does not authorize reuse or editing the shared person.

All browsers show at most 50 records per page, retain collection/search/filter values in record and page links, and select only records on the authorized visible page. An invalid or filtered-out selection falls back to the first visible record; an empty list has no preview actions. Switching collections resets search and collection-specific filters. Selecting a name navigates to the preview, which stacks below the table when space is limited; tables scroll within their own region. Existing assessment/report snapshots and audit history are unchanged.

For Harbor Cafe ownership, select **Alex Morgan** from the contact dropdown rather than typing a name. Use **Notes** for other people involved. If the owner is not yet known, choose **Unassigned**. Add/link a missing person through the **Add contact** button beside the dropdown, return and the **refresh icon**, then select the person. Inventory shares contacts across this customer's engagements; engagement tasks and investigations use only their own engagement's contacts. Ownership does not grant login access or authorize changes.

Form labels and help are consistent in v0.2.4: choose **Customer-facing** from Operation category (its empty label is **Select an operation category**). Open the circled **i** beside any field for its guidance. Owner remains **Unassigned** until a contact is selected. Add contact is a visible button; refreshing is a compact icon. Help dialogs do not submit the form or clear entries.

When testing **Edit** on Orders and payments, use **Cancel** to discard the unsaved form and return to the inventory list. The stored record and history are unchanged. Opening Edit from a filtered inventory view preserves that view on cancellation; Save still records the change and returns to the saved record's collection.

To skip further operation-entry testing after **Orders and payments**, open **Operations → Prefill synthetic Harbor Cafe operations**, choose the optional owner, and press **Add remaining cafe operations**. The three remaining examples appear in the table. If payroll or vendor/rent payments were entered manually, they are retained. The examples stay Unknown/unrated and can be edited later; proceed to providers/devices and their relationships rather than typing the same operation fields again.
