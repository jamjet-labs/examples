# java-oauth-agent

OAuth 2.0 delegated agent — acts on behalf of a user with narrowed scopes.

## Run it

```bash
mvn compile exec:java
```

## What it does

1. Simulates RFC 8693 token exchange (user token to agent token)
2. Enforces scope narrowing — agent can never exceed user's permissions
3. Applies per-step scope requirements (read vs write vs approve)
4. Blocks privilege escalation attempts with clear errors
5. Logs every token operation to an audit trail

## Scenarios

- **Full permissions** — user with `expenses:read,write,approve` submits successfully
- **Read-only user** — scope narrowing removes `expenses:write`, submission blocked
- **No expense scopes** — scope narrowing fails entirely, agent cannot proceed

## Key concepts

- **RFC 8693 token exchange** — agent exchanges user's token for a scoped agent token via the authorization server
- **Scope narrowing** — requested scopes must be a subset of user's scopes
- **Per-step scoping** — `NodeOAuthScopes` lets each workflow node declare required scopes
- **Token validity** — expired or revoked tokens trigger `OAuthError::TokenExpired` / `TokenRevoked`
- **Audit trail** — `OAuthAuditEntry` logs every `token_exchange` and `token_use` operation

## Runtime behavior

On the JamJet runtime, the OAuth module performs real HTTP token exchanges:

```
Agent -> Authorization Server: POST /token (RFC 8693)
  grant_type: urn:ietf:params:oauth:grant-type:token-exchange
  subject_token: <user's access token>
  scope: expenses:read expenses:write
Agent <- Authorization Server: { access_token, expires_in, scope }
```

The runtime's `check_token_validity()` is called before every tool/model invocation.

## Next steps

- [java-multi-tenant](../java-multi-tenant/) — tenant-isolated workflows
- [java-data-governance](../java-data-governance/) — PII detection and redaction
- [java-approval-workflow](../java-approval-workflow/) — human-in-the-loop approval
