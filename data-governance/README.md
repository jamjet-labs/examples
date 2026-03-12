# data-governance

PII-aware customer onboarding with automatic redaction and retention policies.

```
┌────────────────┐     ┌────────────────┐     ┌──────────────────┐
│   detect-pii   │────▶│   kyc-verify   │────▶│ redact-and-store │────▶ end
│                │     │                │     │                  │
│ email, ssn,    │     │ Uses real PII  │     │ Masks all PII    │
│ phone, card    │     │ for identity   │     │ for audit log    │
└────────────────┘     └────────────────┘     └──────────────────┘
                                                       │
                              ┌─────────────────────────┘
                              ▼
                    ╔══════════════════════╗
                    ║   Audit Log Entry    ║
                    ║   redacted: true     ║
                    ║   expires_at: +90d   ║
                    ║   prompts: stripped  ║
                    ╚══════════════════════╝
```

## The Problem

Agents process sensitive customer data (SSN, credit cards, emails) but audit logs and state stores must comply with data protection regulations (GDPR, CCPA, HIPAA). Without automatic PII handling, sensitive data leaks into logs, traces, and snapshots.

## How JamJet's Data Governance Works

The runtime's `PiiRedactor` (in `policy/src/redaction.rs`) applies rules from the workflow's `DataPolicyIr`:

| Feature | How it works |
|---------|-------------|
| **PII detection** | Built-in regex patterns: email, SSN, phone, credit card, IP address |
| **Field-path tagging** | JSON paths like `$.email` mark known PII fields |
| **Redaction modes** | `mask` (partial reveal), `hash` (SHA-256), `remove` (delete field) |
| **Retention controls** | `retention_days` sets `expires_at` on audit entries |
| **Prompt stripping** | `retain_prompts: false` removes prompts from audit log |
| **Output stripping** | `retain_outputs: false` removes model outputs from audit log |
| **Auto-purge** | `purge_expired()` deletes entries past their `expires_at` |

## Run it

```bash
jamjet dev &
jamjet run workflow.yaml --input '{
  "customer_id": "CUST-7291",
  "full_name": "Jane Doe",
  "email": "jane.doe@example.com",
  "phone": "555-123-4567",
  "ssn": "123-45-6789",
  "credit_card": "4111-1111-1111-1234"
}'
```

## What it does

1. **Detect PII** — identifies email, SSN, phone, credit card via regex patterns
2. **KYC verify** — uses real PII for identity verification (audit log gets redacted version)
3. **Redact & store** — masks all PII, generates compliance-safe summary with retention metadata

## Data policy configuration

```yaml
data_policy:
  pii_detectors: [email, ssn, phone, credit_card]
  pii_fields: ["$.email", "$.phone", "$.ssn", "$.credit_card"]
  redaction_mode: mask
  retain_prompts: false
  retain_outputs: false
  retention_days: 90
```

## Python equivalent

See [workflow.py](./workflow.py) for the same workflow using the Python SDK.

## Next steps

- [multi-tenant](../multi-tenant/) — tenant-isolated workflows
- [oauth-delegation](../oauth-delegation/) — OAuth 2.0 delegated agent auth
- [healthcare-compliance](../healthcare-compliance/) — HIPAA-compliant patient intake
- [java-data-governance](../java-data-governance/) — same example in Java
