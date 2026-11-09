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
