# oauth-delegation

OAuth 2.0 delegated agent — acts on behalf of users with narrowed scopes.

```
┌────────────────┐     ┌────────────────┐     ┌───────┐
│  authenticate  │────▶│submit-expense  │────▶│ route │
│                │     │                │     └───┬───┘
│ Token exchange │     │ expenses:write │         │
│ Scope narrowing│     │ required       │    ┌────┴────┐
│ expenses:read  │     │                │    │  >$1k?  │
└────────────────┘     └────────────────┘    └──┬───┬──┘
                                                │   │
     ┌──────────────────────────────────────────┘   └──▶ end
     ▼
┌──────────────────┐
│ manager-approval │
│ expenses:approve │────▶ end
│ (human gate)     │
└──────────────────┘

  Token Exchange (RFC 8693):
  ┌────────┐                    ┌────────────────┐
  │ Agent  │── POST /token ──▶  │ Auth Server    │
  │        │  subject_token     │                │
  │        │  scope: read,write │ Validates user │
  │        │◀── agent_token ──  │ Narrows scopes │
  └────────┘                    └────────────────┘
```

## The Problem

AI agents acting on behalf of users must never exceed the user's permissions. Without delegated auth, agents either get full admin access (dangerous) or users must share credentials (insecure). RFC 8693 token exchange solves this by letting agents obtain narrowly-scoped tokens.

## How JamJet's OAuth Works

| Feature | How it works |
|---------|-------------|
| **Token exchange** | `exchange_token()` — POST to auth server with RFC 8693 parameters |
| **Scope narrowing** | `narrow_scopes()` — agent's requested scopes must be subset of user's |
| **Per-step scoping** | `NodeOAuthScopes` — different nodes request different scope sets |
| **Token validity** | `check_token_validity()` — called before every tool/model invocation |
| **Revocation** | `OAuthError::TokenRevoked` — clean error with escalation to human |
| **Expiry** | `OAuthError::TokenExpired` — token refreshed or workflow paused |
| **Audit trail** | `OAuthAuditEntry` — logs every `token_exchange` and `token_use` |

## Run it

```bash
# Configure OAuth (or use env vars)
export JAMJET_OAUTH_TOKEN_ENDPOINT=https://auth.example.com/token
export JAMJET_OAUTH_CLIENT_ID=expense-agent
export JAMJET_OAUTH_CLIENT_SECRET=your-secret

jamjet dev &
jamjet run workflow.yaml --input '{
  "employee_id": "emp-42",
  "employee_name": "Alice Chen",
  "amount": 350.00,
  "description": "Team lunch",
  "user_scopes": ["expenses:read", "expenses:write"]
}'
```

## What it does

1. **Authenticate** — exchanges user's token for a scoped agent token (expenses:read)
2. **Submit expense** — creates expense entry (requires expenses:write scope)
3. **Route** — expenses > $1k require manager approval
4. **Manager approval** — human gate (requires expenses:approve scope)

## Per-step scope configuration

```yaml
nodes:
  authenticate:
    oauth_scopes:
      required_scopes: ["expenses:read"]

  submit-expense:
    oauth_scopes:
      required_scopes: ["expenses:read", "expenses:write"]

  approval-required:
    oauth_scopes:
      required_scopes: ["expenses:read", "expenses:approve"]
```

## Python equivalent

See [workflow.py](./workflow.py) for the same workflow using the Python SDK.

## Next steps

- [multi-tenant](../multi-tenant/) — tenant-isolated workflows
- [data-governance](../data-governance/) — PII detection and redaction
- [java-oauth-agent](../java-oauth-agent/) — same example in Java
