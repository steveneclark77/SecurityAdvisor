# Repository guidance

## Application versioning

- `VERSION` at the repository root is the single source of truth for the running application version, using `major.minor.patch` SemVer.
- Each user-requested change increments the patch number unless the user explicitly requests a different version or increment.
- Increment once per requested change, not once per file, commit, or fix made while completing that request.
- Keep the header reading the version from the file; do not hardcode it in templates.

## Form interaction

- Disable action buttons until required inputs are complete and valid. Always retain server-side validation. Informational/help buttons must use `type="button"`.

## Code Reviews
Reviewers Prioritize: 
1. Cross-customer access and shared-contact privacy.
2. Assessment/change authorization boundaries.
3. Preservation of baseline, assessment, report, and audit history.
4. Migration safety and retention of existing data.
5. Evidence-upload and expiring-link security.
6. Server-side validation, regardless of disabled UI buttons.
7. Relevant tests are written and executed
8. Requested version increment.

## UI interaction patterns

- Render action links with shared button styling. Use real submit buttons for mutations; preserve safe links for navigation to forms, external references, and record navigation. Do not use GET requests to mutate state.
- Explanatory-only blocks use the distinct `guidance-panel` style and a visible Guidance label, rather than the white card style used for data and controls. Empty states should not look like an available action.

## Form and CSRF regression checks

- Add every application POST route to the shared submission inventory in `testsupport/csrf_cases.py`, with a valid payload and a persisted-outcome assertion.
- Verify legitimate CSRF-protected submission as well as rejection of missing/incorrect tokens and invalid origins.
- Changes to form templates, referrer policies, authentication, or submission behavior require the affected real-browser tests. Do not disable CSRF, bypass browser header behavior, or silently skip unavailable engines.

## Security review follow-up

- For each addressed 0-security finding, reply on its existing PR review thread with a brief description of the code change and associated commit. Resolve the thread after verifying the fix.
- Inspect existing finding threads even when the latest scan reports no findings; leave findings open until their code fixes are verified.

## DRY and shared styling

- Prioritize DRY in every coding task: reuse and improve existing helpers, components, templates, and styles before introducing parallel implementations.
- Keep all first-party CSS in shared static stylesheets. Do not add embedded `<style>` blocks, `style` attributes, or JavaScript-generated CSS; use reusable classes and class toggles.
- Share component rules and typography across public and consultant pages. Keep genuinely different page layouts in their layout stylesheet, using the common stylesheet include.
