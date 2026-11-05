"""Original actionable starter guidance; thematic references are not certification mappings."""

# Each tuple is an instruction, applicability/exception guidance, and verification.
ACTIONS = {
    'GOV-01': [
        ('Name an accountable security owner and a business decision-maker who can accept residual risk.', 'All businesses; an external adviser can assist but does not replace business accountability.', 'Confirm named owners and delegates accept their documented responsibilities.'),
        ('Schedule risk reviews and record decisions, owners, deadlines, and accepted exceptions.', 'Set frequency according to business change; review again after major incidents or technology changes.', 'Inspect a completed review and follow one action through to closure.'),
        ('Document critical operations, outage tolerances, and escalation contacts.', 'Include financial, availability, reputation, privacy, and safety consequences where relevant.', 'Have business owners confirm thresholds and test contact availability without initiating an incident.'),
    ],
    'ID-01': [
        ('Inventory devices, applications, cloud tenants, domains, external services, and their owners.', 'Include remote devices and outsourced services; use records or interviews where automated discovery is unavailable.', 'Reconcile a sample of purchases, DNS records, and user-reported services with the inventory.'),
        ('Record support status, business criticality, sensitive-data use, and upstream dependencies.', 'Use customer-specific criticality; do not store passwords or tokens in the inventory.', 'Trace a critical business process to its systems, providers, and responsible owners.'),
        ('Update the inventory during onboarding, purchasing, changes, and retirement.', 'Assign an owner and periodic reconciliation schedule appropriate to business change.', 'Inspect a recent addition and retirement, including removal of access and retained data.'),
    ],
    'PR-01': [
        ('Inventory corporate identity services and critical accounts, starting with email, source repositories, cloud administrators, and the identity provider.', 'Include local accounts, contractors, and accounts outside centralized sign-in. Do not collect credentials.', 'Compare a redacted account export with the application inventory and named owners.'),
        ('Require phishing-resistant MFA for privileged accounts first, then expand coverage using FIDO2/WebAuthn passkeys or hardware security keys.', 'Check provider and account support. SMS and one-time codes are not phishing-resistant; document temporary exceptions where stronger methods are unavailable.', 'Review enforced authentication methods and safely test that a weaker method cannot satisfy the privileged sign-in policy.'),
        ('Protect enrollment and recovery so weaker fallback methods cannot bypass the authentication requirement.', 'Provide accessible recovery procedures and a second protected authenticator. Phishing resistance reduces credential phishing but does not eliminate session theft or endpoint compromise.', 'Review reset permissions, recovery methods, and a controlled recovery exercise without collecting secrets.'),
        ('Where appropriate, require managed, compliant devices for privileged access and pilot enforcement before wider rollout.', 'Device compliance is separate from MFA. Synced passkeys are not necessarily device-bound. Check licensing, device-management prerequisites, contractor exceptions, and emergency access.', 'With authorized test accounts, compare compliant and unmanaged-device access and confirm documented exceptions.'),
        ('Remove unnecessary privileges and use separate administrative identities for privileged work.', 'Small teams may combine roles, but should separate routine activity from administrative sessions where supported.', 'Sample administrator assignments and confirm each has an owner and a business justification.'),
        ('Use an offboarding checklist to disable accounts, revoke sessions and tokens, and transfer business ownership promptly.', 'Cover federated and standalone services, service credentials, and scheduled access expiration for contractors.', 'Trace a recent departure across critical services and verify session and token revocation records.'),
        ('Maintain protected emergency access and rehearse recovery before enforcing restrictive policies.', 'Follow provider-supported emergency access guidance; monitor use and protect credentials outside this application.', 'Review emergency access monitoring and evidence of a controlled recovery test.'),
    ],
    'PR-02': [
        ('List internet-facing services and remove or restrict services that lack a business need.', 'Use inventory and authorized configuration review; intrusive scanning requires separate authorization.', 'Compare external exposure records with approved services and owners.'),
        ('Track software support dates and prioritize applicable actively exploited vulnerabilities and exposed systems.', 'Set remediation deadlines by customer risk; isolate unsupported systems if immediate replacement is impractical.', 'Sample installed versions against vendor advisories and review dated exception decisions.'),
        ('Test updates, arrange recovery or rollback, deploy in a controlled sequence, and confirm completion.', 'Operational or safety-critical systems require vendor-approved maintenance windows and compensating safeguards.', 'Inspect deployment results and confirm affected versions changed, including failed or offline devices.'),
    ],
    'PR-03': [
        ('Inventory legitimate mail senders and configure SPF and DKIM for authorized services.', 'Include marketing and transactional mail; avoid breaking legitimate senders or exceeding SPF DNS lookup limits.', 'Inspect DNS and redacted headers from representative legitimate messages for authentication results.'),
        ('Monitor DMARC reports, correct sender alignment, and progress to quarantine or reject when legitimate mail is accounted for.', 'Pilot changes and monitor delivery. Domain authentication does not stop lookalike domains or all phishing.', 'Review alignment results, policy enforcement, delivery impact, and recorded exceptions.'),
        ('Provide a simple phishing-reporting route and independently verify payment or bank-detail changes.', 'Use a known contact method, not contact details supplied in the suspicious message; include delegated payment staff.', 'Walk through a safe simulated report and payment-change request and inspect the response.'),
    ],
    'PR-04': [
        ('Require supported operating systems, automatic locking, full-disk encryption, and securely stored recovery keys.', 'Confirm recovery access before enforcement; document safeguards for equipment that cannot support encryption.', 'Review a representative device sample and redacted policy coverage, without copying recovery keys.'),
        ('Manage endpoint safeguards and updates centrally where practical and remove unnecessary local administrator rights.', 'Select safeguards appropriate to platform and business size; document justified administrative exceptions.', 'Inspect health and update reports and verify a standard user cannot perform an unapproved administrative change.'),
        ('Define lost-device reporting, remote access revocation, and approved lock or wipe procedures.', 'Separate personal and business data on BYOD devices; obtain authorization before destructive actions.', 'Run a tabletop loss scenario and confirm the owner can identify the device and revoke its business access.'),
    ],
    'PR-05': [
        ('Map sensitive information to storage, transfers, owners, and business purposes; stop unnecessary collection.', 'Include SaaS exports, shared drives, and providers; confirm legal and contractual requirements with qualified advisers.', 'Trace a sample information flow and confirm why each retained copy is necessary.'),
        ('Restrict sharing and access by role, remove unnecessary public links, and protect data in transit and at rest.', 'Use supported encryption and managed keys; document necessary external sharing and review expiration.', 'Review redacted sharing settings and test access with authorized low-privilege accounts.'),
        ('Define retention triggers, approved exceptions, and secure deletion covering exports and backup lifecycle.', 'Apply customer-specific obligations. SecurityAdvisor requires three-year retention, but the starting event and exceptions still need agreement.', 'Review a sample retention decision and deletion evidence, including how expiring backups are handled.'),
    ],
    'GOV-02': [
        ('Identify critical providers, named internal owners, data handled, and shared security responsibilities.', 'Include platforms such as Shopify and outsourced IT; outsourcing does not transfer all business accountability.', 'Inspect a critical provider record and confirm both parties understand their responsibilities.'),
        ('Review contractual incident notification, recovery commitments, access safeguards, and available assurance evidence.', 'Scale diligence to dependency and data sensitivity; provider certifications do not prove every customer configuration is secure.', 'Compare documented requirements with current contracts, assurance scope, and tenant settings.'),
        ('Document outage workarounds, export capability, and access/data removal at termination.', 'Where no practical substitute exists, document accepted dependency risk and continuity arrangements.', 'Test an authorized non-sensitive export and walk through provider outage and termination scenarios.'),
    ],
    'DE-01': [
        ('Enable relevant identity, administrative, endpoint, and critical-service logs and protect them from unauthorized alteration.', 'Balance detection needs, privacy, storage cost, and contractual retention; avoid logging credentials.', 'Review coverage, timestamps, access permissions, and retention for representative systems.'),
        ('Route actionable alerts for suspicious sign-ins, privilege changes, and disabled safeguards to a named responder.', 'Set thresholds and escalation hours appropriate to business exposure; use a provider if internal coverage is unavailable.', 'Create an authorized benign test event and confirm receipt, acknowledgment, and escalation.'),
        ('Review alert quality and investigate gaps, excessive noise, and missing telemetry.', 'Set a review schedule and repeat after significant system changes.', 'Inspect a recent investigation and confirm corrective actions address missed or noisy signals.'),
    ],
    'RS-01': [
        ('Prepare an accessible response plan with roles, trusted contacts, escalation, and decision authority.', 'Include IT providers, business leaders, legal/insurance contacts where relevant, and an offline copy.', 'Confirm contact accuracy and that responders can retrieve the plan if primary systems are unavailable.'),
        ('Document containment and evidence-preservation steps for account takeover, ransomware, and vendor incidents.', 'Use authorized procedures; consider safety and business impact before isolating systems or deleting evidence.', 'Walk through who can revoke sessions, isolate affected systems, and preserve useful logs.'),
        ('Define customer and authority communication responsibilities and exercise the plan.', 'Notification obligations depend on jurisdiction, contracts, and incident facts; obtain appropriate advice.', 'Run a tabletop exercise and track owners and deadlines for identified improvements.'),
    ],
    'RC-01': [
        ('Define recovery time and acceptable data-loss targets for critical business processes.', 'Targets must come from business owners and account for provider dependencies and cost.', 'Compare documented recovery objectives with dependency and backup coverage.'),
        ('Back up critical data and configurations with copies protected from production-account compromise.', 'Use offline or appropriately configured immutable copies where suitable; protect recovery credentials and retention settings.', 'Review backup coverage and permissions and confirm production administrators cannot casually remove every recovery copy.'),
        ('Test restoration in isolation and record elapsed time, recovered data integrity, and missing dependencies.', 'Use non-production targets and safe sample data; include SaaS exports where provider recovery is insufficient.', 'Inspect current restore evidence and compare measured results with recovery objectives.'),
    ],
    'SW-01': [
        ('Inventory coding agents, extensions, installation hooks, and automated tool integrations with their publishers and permissions.', 'Applies to software development and other use of coding agents; distinguish built-in functions from separately installed tools.', 'Inspect a representative environment and reconcile installed tools with the approved list.'),
        ('Review tool provenance and requested access before installation or updates; restrict unapproved automatic installations.', 'Follow supported product controls. Review plugins, package scripts, and agent configuration rather than assuming a trusted application makes every integration safe.', 'In an isolated test environment, confirm an unapproved extension or installation hook requires review or is blocked.'),
        ('Limit developer-tool access to repositories, credentials, filesystem paths, and networks needed for the task.', 'Use sandboxing and scoped short-lived access where supported; do not place production secrets in prompts or test fixtures.', 'Inspect effective permissions and run authorized harmless boundary tests with synthetic data.'),
        ('Keep a removal and incident procedure for unsafe tools, including revocation of exposed tokens and review of executed changes.', 'Do not assume uninstalling a plugin reverses code execution or credential exposure.', 'Exercise removal with a test tool and verify related access is revoked and relevant logs are retained.'),
    ],
    'PAY-01': [
        ('Map payment entry points and determine whether card information touches business systems or only provider-hosted services.', 'Include in-person terminals, online checkout, support channels, and third-party scripts.', 'Trace a representative transaction without collecting real card details and document the boundary.'),
        ('Confirm applicable PCI responsibilities and validation requirements with the payment provider or qualified adviser.', 'A hosted checkout may reduce scope but does not automatically remove merchant obligations.', 'Retain current responsibility and scope documentation without claiming unsupported compliance.'),
        ('Protect payment administration with phishing-resistant MFA where supported and independently verify payout changes.', 'Apply account-recovery safeguards and separation of approval duties where staffing permits.', 'Review administrative access and walk through a test payout-change approval using synthetic information.'),
    ],
    'OT-01': [
        ('Inventory operational equipment and dependencies, including vendor remote access and safety constraints.', 'Include unsupported equipment and facilities systems; obtain operator involvement before testing.', 'Review equipment records and operator-confirmed network diagrams without intrusive discovery.'),
        ('Separate operational networks from ordinary business access and allow only documented necessary connections.', 'Design changes with equipment vendors and safety owners; use compensating controls when replacement is impractical.', 'Review firewall rules and approved flows; validate boundaries through an authorized safe procedure.'),
        ('Require approved, time-limited vendor access with strong authentication where supported and log its use.', 'Avoid unrestricted permanent access; document legacy limitations and supervised alternatives.', 'Review a vendor session and demonstrate removal or expiration of access without disrupting equipment.'),
        ('Plan vendor-supported maintenance, configuration backups, and recovery exercises.', 'Use approved maintenance windows and non-production exercises; do not apply disruptive generic IT tests to live equipment.', 'Inspect maintenance decisions and a documented safe recovery exercise.'),
    ],
}

REFERENCES = {
    'PR-01': 'NIST digital identity guidance: https://pages.nist.gov/800-63-4/\nCISA phishing-resistant MFA guidance: https://www.cisa.gov/resources-tools/resources/implementing-phishing-resistant-mfa',
    'PR-03': 'DMARC specification and security considerations: https://www.rfc-editor.org/rfc/rfc7489',
    'PR-02': 'CISA Known Exploited Vulnerabilities catalog (confirm product applicability): https://www.cisa.gov/known-exploited-vulnerabilities-catalog',
    'SW-01': 'OWASP secure development guidance: https://owaspsamm.org/\nNIST Secure Software Development Framework: https://csrc.nist.gov/projects/ssdf',
    'PAY-01': 'PCI SSC standards and merchant applicability resources: https://www.pcisecuritystandards.org/',
    'OT-01': 'NIST operational technology security guidance: https://csrc.nist.gov/pubs/sp/800/82/r3/final',
}
