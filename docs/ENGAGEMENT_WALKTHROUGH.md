# Running a synthetic customer engagement

This walkthrough is for a consultant-led exercise, not a completed assessment. Do not use real customer data yet. No customer, baseline approval, finding, or remediation result is automatically created by installation or update.

## 1. Prepare the application and library

Apply the update with `./update.command` on macOS, or follow the manual rebuild/migration commands in SETUP.md. Sign in using your consultant account and open **Customer engagements** from the top navigation.

Before creating an assessment, use **Library** to review starter controls and capture a baseline. Record the incomplete framework mappings and any missing coverage. Review coverage, applicability, references, and limitations separately before approving. An approval for a synthetic exercise is not a compliance claim or evidence of complete coverage.

If changes are needed before approval, choose **Revise this draft**, edit and save the working guidance in the linked admin pages, then return and capture a uniquely named replacement. The original becomes **Superseded** and links to the replacement; review and approve the replacement separately. The revision captures the current shared working library and does not silently restore the old snapshot.

## 2. Create the customer and scope

Choose **Create synthetic customer**, name it **Synthetic Harbor Cafe**, and confirm that the records contain no real information. The creating user is assigned to that customer; other staff users do not automatically receive access, including superusers through customer workflow screens. No customer models are exposed through the global admin.

Create an engagement such as **Initial security improvement exercise**:

- Scope: fictional email administration, hosted ordering, payment administration, and business laptops.
- Exclusions: intrusive scanning, live payment processing, and changes to real services.
- Contact: a fictional business owner.
- Assessment authorization: fictional owner authorized interviews, synthetic configuration review, and safe test-account demonstrations.
- Change authorization: initially leave blank. Assessment permission does not authorize remediation.
- Deliverables: executive summary, technical findings, and a prioritized plan.
- Business context: describe the cafe's critical operations, outage tolerance, reputation concerns, and financial impact thresholds. Record unknown thresholds explicitly rather than inventing certainty.
- Follow-up: choose a review date and triggers such as a provider change, new location, or relevant incident.

Three-year retention is a requirement, not automated deletion. Its starting event, backup treatment, and exceptions remain undecided.

## 3. Exercise intake

Create an expiring intake link. The application shows a relative path once; copy it or open it locally to role-play the customer. The link lasts seven days, is scoped to intake, and is consumed after final submission. Save progress before final submission to test resuming.

Choose restaurants/food service, payment processing, and any other exposures relevant to the fictional business. Describe services and business consequences, using the unknowns field for unresolved questions.

Return to the engagement page to review the provisional profile recommendation. It uses the customer's selected business activity and exposures, not an AI determination. A mixed or unknown industry produces an explicitly provisional fallback. Intake does not overwrite the consultant's business context.

External customers cannot reach a laptop-only deployment. Do not expose the development server to the internet to test intake.

## 4. Start and review an assessment

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

Open the review queue to plan a dated reassessment or dismiss it with a rationale. Start a new assessment from the newer baseline if needed. Daily news ingestion is still pending the source list and classification design; approved library changes already exercise the reassessment path.

## Feedback to capture during the exercise

Record confusing questions, missing evidence examples, awkward navigation, excessive repeated entry, unclear risk definitions, grouping problems, and report omissions. Distinguish a workflow problem from a scenario where the underlying facts are simply unknown. We will refine the application after this exercise.
