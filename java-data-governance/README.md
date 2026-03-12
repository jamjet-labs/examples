# java-data-governance

PII-aware customer onboarding with automatic redaction and retention policies.

## Run it

```bash
mvn compile exec:java
```

## What it does

1. Accepts customer data containing PII (email, SSN, phone, credit card)
2. Detects PII fields using the same regex patterns as the runtime
3. Performs KYC verification using the real data
4. Redacts all PII fields (masking) before storage
5. Produces a safe, redacted summary for the audit log

## Key concepts

- **PII detection** — built-in patterns for email, SSN, phone, credit card, IP address
- **Redaction modes** — mask (partial reveal), hash (SHA-256), or remove
- **Data retention** — `retention_days` controls automatic audit entry expiry via `purge_expired()`
- **Audit safety** — `retain_prompts: false` and `retain_outputs: false` strip sensitive content from logs
- **DataPolicyIr** — workflow-level and node-level data handling policy in the IR

## Runtime data policy

When submitted to the JamJet runtime, the `DataPolicyIr` in the workflow IR controls automatic PII handling:

```yaml
data_policy:
  pii_detectors: [email, ssn, phone, credit_card]
  redaction_mode: mask
  retain_prompts: false
  retain_outputs: false
  retention_days: 90
```

## Next steps

- [java-multi-tenant](../java-multi-tenant/) — tenant-isolated workflows
- [java-oauth-agent](../java-oauth-agent/) — OAuth 2.0 delegated auth
- [healthcare-compliance](../healthcare-compliance/) — HIPAA-compliant patient intake
