# Open topics

## Record-name uniqueness

Decide whether names should be unique for any record types within an engagement
or customer. Names currently remain non-unique; this topic does not authorize a
schema or validation change.

Consider:

- Which record types benefit from unique names, and whether the scope is the
  engagement, customer, or another collection.
- Whether comparisons ignore capitalization and surrounding whitespace.
- Whether a duplicate-name warning and distinguishing context (owner, location,
  date, asset identifier) would be more useful than blocking duplicate names.
- How archived records, repeated issues, imports, and historical snapshots should
  behave if a uniqueness rule is introduced.

Current recommendation for later review: allow duplicate display names and use
unique identifiers where needed. Confirm the policy by record type before coding.
