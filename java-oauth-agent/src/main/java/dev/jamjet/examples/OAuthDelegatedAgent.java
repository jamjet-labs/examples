package dev.jamjet.examples;

import dev.jamjet.ir.IrValidator;
import dev.jamjet.workflow.Workflow;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * OAuth 2.0 delegated agent: acts on behalf of a user with narrowed scopes.
 *
 * <p>Demonstrates JamJet's OAuth 2.0 enterprise features (Phase 4.17–4.21):
 * <ul>
 *   <li>RFC 8693 token exchange — agent exchanges user's token for a scoped agent token</li>
 *   <li>Scope narrowing — agent can never exceed the user's permissions</li>
 *   <li>Per-step scoping — different workflow steps request different scope sets</li>
 *   <li>Token validity checks — expired/revoked tokens trigger clean errors</li>
 *   <li>Audit trail — every token exchange and API call is logged</li>
 * </ul>
 *
 * <p>When running on the JamJet runtime, the OAuth module performs real
 * RFC 8693 token exchanges with your authorization server. This example
 * shows the scope narrowing and per-step scoping logic locally.
 *
 * <pre>
 *   mvn compile exec:java
 * </pre>
 */
public class OAuthDelegatedAgent {

    // ── Token model (mirrors runtime's AgentToken) ───────────────────────────

    record AgentToken(
            String accessToken,
            String tokenType,
            Instant expiresAt,
            Set<String> scopes,
            String agentId,
            String userId,
            boolean revoked
    ) {
        boolean isValid() {
            return !revoked && (expiresAt == null || Instant.now().isBefore(expiresAt));
        }

        boolean hasScope(String scope) {
            return scopes.contains(scope);
        }

        boolean hasAllScopes(String... required) {
            return Set.of(required).stream().allMatch(scopes::contains);
        }
    }

    record AuditEntry(String operation, String agentId, String userId,
                      Set<String> scopes, String target, boolean success) {}

    // ── State ─────────────────────────────────────────────────────────────────

    record ExpenseState(
            String employeeId,
            String employeeName,
            double amount,
            String description,
            List<String> userScopes,
            List<String> effectiveScopes,
            String tokenStatus,
            String result,
            List<AuditEntry> auditTrail
    ) {}

    // ── Scope narrowing (mirrors runtime's narrow_scopes) ────────────────────

    static List<String> narrowScopes(List<String> requested, List<String> userScopes) {
        var userSet = Set.copyOf(userScopes);
        var narrowed = requested.stream().filter(userSet::contains).toList();
        if (narrowed.isEmpty() && !requested.isEmpty()) {
            throw new SecurityException(
                    "Scope narrowing failed: requested %s but user only has %s"
                            .formatted(requested, userScopes));
        }
        return narrowed;
    }

    // ── Per-step scope config ────────────────────────────────────────────────

    static final Map<String, List<String>> STEP_SCOPES = Map.of(
            "read_expenses", List.of("expenses:read"),
            "submit_expense", List.of("expenses:read", "expenses:write"),
            "approve_expense", List.of("expenses:read", "expenses:approve")
    );

    // ── Main ──────────────────────────────────────────────────────────────────

    public static void main(String[] args) {
        var workflow = Workflow.<ExpenseState>builder("oauth-expense-agent")
                .version("0.1.0")
                .state(ExpenseState.class)

                // Step 1: Exchange user token and narrow scopes
                .step("authenticate", state -> {
                    // The runtime performs a real RFC 8693 token exchange here.
                    // We simulate the scope narrowing logic.
                    var requested = List.of("expenses:read", "expenses:write");
                    List<String> effective;
                    String tokenStatus;

                    try {
                        effective = narrowScopes(requested, state.userScopes());
                        tokenStatus = "valid";
                    } catch (SecurityException e) {
                        effective = List.of();
                        tokenStatus = "scope-narrowing-failed";
                    }

                    var audit = new AuditEntry("token_exchange", "expense-agent",
                            state.employeeId(), Set.copyOf(effective),
                            "expenses-api", !effective.isEmpty());

                    return new ExpenseState(
                            state.employeeId(), state.employeeName(),
                            state.amount(), state.description(),
                            state.userScopes(), effective, tokenStatus,
                            null, List.of(audit));
                })

                // Step 2: Submit the expense (requires expenses:write)
                .step("submit_expense", state -> {
                    if (!"valid".equals(state.tokenStatus())) {
                        return new ExpenseState(
                                state.employeeId(), state.employeeName(),
                                state.amount(), state.description(),
                                state.userScopes(), state.effectiveScopes(),
                                state.tokenStatus(), "blocked: invalid token",
                                state.auditTrail());
                    }

                    // Check per-step scopes
                    var required = STEP_SCOPES.get("submit_expense");
                    var hasScopes = state.effectiveScopes().containsAll(required);

                    var audit = new AuditEntry("token_use", "expense-agent",
                            state.employeeId(), Set.copyOf(state.effectiveScopes()),
                            "POST /expenses", hasScopes);

                    var trail = new java.util.ArrayList<>(state.auditTrail());
                    trail.add(audit);

                    if (!hasScopes) {
                        return new ExpenseState(
                                state.employeeId(), state.employeeName(),
                                state.amount(), state.description(),
                                state.userScopes(), state.effectiveScopes(),
                                state.tokenStatus(),
                                "blocked: insufficient scopes for submit",
                                trail);
                    }

                    return new ExpenseState(
                            state.employeeId(), state.employeeName(),
                            state.amount(), state.description(),
                            state.userScopes(), state.effectiveScopes(),
                            state.tokenStatus(),
                            "submitted: expense $%.2f for %s".formatted(
                                    state.amount(), state.description()),
                            trail);
                })

                .build();

        // Compile and validate
        var ir = workflow.compile();
        IrValidator.validateOrThrow(ir);

        System.out.println("=== OAuth 2.0 Delegated Agent: Expense Processing ===");
        System.out.println("Workflow:  " + ir.id());
        System.out.println("Version:   " + ir.version());
        System.out.println();

        // --- Scenario 1: User has full scopes ---
        System.out.println("--- Scenario 1: User with full permissions ---");
        var fullUser = new ExpenseState(
                "emp-42", "Alice Chen", 350.00, "Team lunch",
                List.of("expenses:read", "expenses:write", "expenses:approve"),
                List.of(), null, null, List.of());
        var result1 = workflow.run(fullUser);
        printResult(result1.state());

        // --- Scenario 2: Read-only user tries to submit ---
        System.out.println("--- Scenario 2: Read-only user (scope narrowing blocks write) ---");
        var readOnlyUser = new ExpenseState(
                "emp-99", "Bob Smith", 150.00, "Office supplies",
                List.of("expenses:read"),
                List.of(), null, null, List.of());
        var result2 = workflow.run(readOnlyUser);
        printResult(result2.state());

        // --- Scenario 3: Privilege escalation attempt ---
        System.out.println("--- Scenario 3: User with no expense scopes (blocked) ---");
        var noScopes = new ExpenseState(
                "emp-00", "Eve Hacker", 99999.99, "Definitely legit",
                List.of("reports:read"),
                List.of(), null, null, List.of());
        try {
            workflow.run(noScopes);
        } catch (Exception e) {
            System.out.println("  Blocked: " + e.getMessage());
            System.out.println("  The agent cannot escalate beyond the user's permissions.");
        }
        System.out.println();

        // --- Per-step scope table ---
        System.out.println("--- Per-Step OAuth Scopes ---");
        STEP_SCOPES.forEach((step, scopes) ->
                System.out.println("  %-20s %s".formatted(step + ":", scopes)));
        System.out.println();
        System.out.println("  When running on the JamJet runtime, each workflow node");
        System.out.println("  can declare required OAuth scopes via NodeOAuthScopes.");
        System.out.println("  The runtime performs real RFC 8693 token exchanges and");
        System.out.println("  enforces scope narrowing at every step.");
    }

    private static void printResult(ExpenseState state) {
        System.out.println("  User:     " + state.employeeName() + " (" + state.employeeId() + ")");
        System.out.println("  Scopes:   " + state.userScopes());
        System.out.println("  Narrowed: " + state.effectiveScopes());
        System.out.println("  Token:    " + state.tokenStatus());
        System.out.println("  Result:   " + state.result());
        System.out.println("  Audit trail:");
        for (var entry : state.auditTrail()) {
            System.out.println("    - %s | %s | scopes=%s | success=%s"
                    .formatted(entry.operation(), entry.target(), entry.scopes(), entry.success()));
        }
        System.out.println();
    }
}
