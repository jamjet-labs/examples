"""
oauth-delegation: OAuth 2.0 delegated agent with scope narrowing.

Demonstrates JamJet's OAuth 2.0 features (Phase 4.17-4.21):
  - RFC 8693 token exchange (user token → scoped agent token)
  - Scope narrowing (agent never exceeds user's permissions)
  - Per-step scope configuration (NodeOAuthScopes)
  - Token validity checks (expired/revoked → OAuthError)
  - OAuth audit trail (OAuthAuditEntry)

Usage:
    jamjet dev &
    jamjet run workflow.py --input '{
        "employee_id": "emp-42",
        "employee_name": "Alice Chen",
        "amount": 350.00,
        "description": "Team lunch",
        "user_scopes": ["expenses:read", "expenses:write", "expenses:approve"]
    }'

Runtime configuration (env vars):
    JAMJET_OAUTH_TOKEN_ENDPOINT=https://auth.example.com/token
    JAMJET_OAUTH_CLIENT_ID=expense-agent
    JAMJET_OAUTH_CLIENT_SECRET=...
"""

from jamjet import workflow, node, State


@workflow(
    id="oauth-expense-agent",
    version="0.1.0",
    # ── OAuth config: RFC 8693 token exchange ───────────────────────
    # The runtime's exchange_token() performs the HTTP call to the
    # authorization server. Scope narrowing is enforced automatically.
    oauth={
        "token_endpoint": "${JAMJET_OAUTH_TOKEN_ENDPOINT}",
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "client_id": "${JAMJET_OAUTH_CLIENT_ID}",
        "client_secret": "${JAMJET_OAUTH_CLIENT_SECRET}",
        "subject_token_source": "workflow_context",
        "requested_scopes": ["expenses:read", "expenses:write"],
        "audience": "https://api.example.com/expenses",
    },
    policy={
        "blocked_tools": ["delete_expense", "modify_approval"],
        "model_allowlist": ["claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
    },
)
class OAuthExpenseAgent:
    """Expense processing agent acting on behalf of users via OAuth delegation.

    The runtime performs real RFC 8693 token exchanges:

        Agent → Auth Server: POST /token
          grant_type: urn:ietf:params:oauth:grant-type:token-exchange
          subject_token: <user's access token>
          scope: expenses:read expenses:write
        Agent ← Auth Server: { access_token, expires_in, scope }

    Scope narrowing ensures the agent token is always ⊆ user's scopes.
    check_token_validity() runs before every tool/model invocation.
    """

    @node(start=True, oauth_scopes=["expenses:read"])
    async def authenticate(self, state: State) -> State:
        """Exchange user token and narrow scopes.

        The runtime's narrow_scopes() enforces:
        - requested scopes must be a subset of user's scopes
        - if no intersection exists → OAuthError::ScopeNarrowingFailed
        - partial matches are allowed (granted scopes = intersection)

        OAuthAuditEntry logged: operation=token_exchange
        """
        response = await self.model(
            model="claude-haiku-4-5-20251001",
            system=(
                "You are an expense processing agent. Your token has been "
                f"narrowed to: {state.get('effective_scopes', [])}. "
                "You cannot escalate privileges."
            ),
            prompt=(
                f"Employee: {state['employee_name']} ({state['employee_id']})\n"
                f"Amount: ${state['amount']:.2f}\n"
                f"Description: {state['description']}\n\n"
                f"Confirm permissions for expense processing."
            ),
        )
        return {"token_status": response.text}

    @node(oauth_scopes=["expenses:read", "expenses:write"])
    async def submit_expense(self, state: State) -> State:
        """Submit the expense. Requires expenses:write scope.

        The runtime checks per-step scopes via resolve_node_scopes():
        1. Reads oauth_scopes from NodeOAuthScopes config
        2. Merges with agent-level OAuthConfig
        3. Applies narrow_scopes() against user's available scopes
        4. If insufficient → blocks with clear error

        OAuthAuditEntry logged: operation=token_use, target=POST /expenses
        """
        response = await self.model(
            model="claude-sonnet-4-6",
            system=(
                f"You are acting on behalf of {state['employee_name']}. "
                f"Your token is scoped to: {state.get('effective_scopes', [])}. "
                "Submit the expense and return confirmation."
            ),
            prompt=(
                f"Submit expense:\n"
                f"  Employee: {state['employee_name']}\n"
                f"  Amount: ${state['amount']:.2f}\n"
                f"  Description: {state['description']}\n\n"
                f"Create the expense entry."
            ),
        )
        return {"expense_status": response.text}

    @node(human_approval=True, timeout="48h",
          oauth_scopes=["expenses:read", "expenses:approve"])
    async def manager_approval(self, state: State) -> State:
        """Manager approval for expenses > $1000.

        This node requires expenses:approve scope, which is different
        from the submit step's expenses:write scope. The runtime
        re-evaluates scopes per-step via resolve_node_scopes().

        If the agent's token has been revoked during execution:
        - check_token_validity() returns OAuthError::TokenRevoked
        - Workflow escalates to human with a clear error message
        """
        return {"expense_status": "approved by manager"}

    @node
    async def finalize(self, state: State) -> State:
        """Generate confirmation."""
        response = await self.model(
            model="claude-haiku-4-5-20251001",
            prompt=(
                f"Expense ${state['amount']:.2f} for {state['description']} "
                f"by {state['employee_name']} — {state.get('expense_status', 'processed')}. "
                f"Generate brief confirmation."
            ),
        )
        return {"expense_status": response.text}
