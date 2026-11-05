# Repository guidance

## Application versioning

- `VERSION` at the repository root is the single source of truth for the running application version, using `major.minor.patch` SemVer.
- Each user-requested change increments the patch number unless the user explicitly requests a different version or increment.
- Increment once per requested change, not once per file, commit, or fix made while completing that request.
- Keep the header reading the version from the file; do not hardcode it in templates.

## Form interaction

- Disable action buttons until required inputs are complete and valid. Always retain server-side validation. Informational/help buttons must use `type="button"`.
