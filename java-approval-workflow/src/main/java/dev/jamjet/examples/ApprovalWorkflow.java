package dev.jamjet.examples;

import dev.jamjet.JamjetClient;
import dev.jamjet.client.ClientConfig;
import dev.jamjet.ir.IrValidator;
import dev.jamjet.workflow.Workflow;

import java.util.Map;

/**
 * Expense approval workflow: prepare, review, approve/reject, notify.
 *
 * <p>Java equivalent of the {@code approval-workflow/} YAML example.
 * Demonstrates workflow compilation, IR validation, and submission to the runtime.
 *
 * <p>This example compiles the workflow to IR and submits it to a running
 * JamJet runtime. The approval step pauses execution until a human
 * approves or rejects via the API.
 *
 * <pre>
 *   jamjet dev &amp;   # start runtime first
 *   mvn compile exec:java
 * </pre>
 */
public class ApprovalWorkflow {

    // ── State ─────────────────────────────────────────────────────────────────

    record ExpenseState(
            String employeeName,
            double amount,
            String description,
            String category,
            boolean requiresApproval,
            String decision,
            String notificationSent
    ) {}

    // ── Main ──────────────────────────────────────────────────────────────────

    public static void main(String[] args) {
        // Build the workflow
        var workflow = Workflow.<ExpenseState>builder("expense-approval")
                .version("0.1.0")
                .state(ExpenseState.class)

                // Step 1: Prepare the expense request
                .step("prepare", state -> {
                    var category = state.amount() > 1000 ? "large" : "small";
                    var requiresApproval = state.amount() > 500;
                    return new ExpenseState(
                            state.employeeName(), state.amount(), state.description(),
                            category, requiresApproval, null, null);
                })

                // Step 2: Auto-approve or flag for review
                .step("review", state -> {
                    if (!state.requiresApproval()) {
                        return new ExpenseState(
                                state.employeeName(), state.amount(), state.description(),
                                state.category(), false, "auto-approved", null);
                    }
                    // In the runtime, this would be a human_approval node that pauses.
                    // For local execution, we simulate approval.
                    return new ExpenseState(
                            state.employeeName(), state.amount(), state.description(),
                            state.category(), true, "pending", null);
                })

                // Step 3: Process the decision
                .step("process", state -> {
                    var decision = state.decision();
                    if ("pending".equals(decision)) {
                        // Simulate manager approval for demo
                        decision = "approved";
                    }
                    var notification = switch (decision) {
                        case "approved", "auto-approved" -> "Expense $%.2f approved for %s"
                                .formatted(state.amount(), state.employeeName());
                        case "rejected" -> "Expense $%.2f rejected for %s"
                                .formatted(state.amount(), state.employeeName());
                        default -> "Unknown decision: " + decision;
                    };
                    return new ExpenseState(
                            state.employeeName(), state.amount(), state.description(),
                            state.category(), state.requiresApproval(), decision, notification);
                })

                .build();

        // Compile and validate
        var ir = workflow.compile();
        IrValidator.validateOrThrow(ir);

        System.out.println("Workflow:  " + ir.id());
        System.out.println("Version:   " + ir.version());
        System.out.println("Nodes:     " + ir.nodes().size());
        System.out.println("Edges:     " + ir.edges().size());
        System.out.println();

        // Local execution demo
        System.out.println("--- Local Execution (small expense, auto-approved) ---");
        var small = new ExpenseState("Alice", 250.00, "Office supplies", null, false, null, null);
        var result1 = workflow.run(small);
        printResult(result1.state());

        System.out.println("--- Local Execution (large expense, requires approval) ---");
        var large = new ExpenseState("Bob", 5000.00, "Conference tickets", null, false, null, null);
        var result2 = workflow.run(large);
        printResult(result2.state());

        // Submit to runtime (if running)
        System.out.println("--- Runtime Submission ---");
        try (var client = new JamjetClient()) {
            client.createWorkflow(ir.toMap());
            System.out.println("Workflow submitted to runtime.");

            var exec = client.startExecution("expense-approval",
                    Map.of("employeeName", "Carol", "amount", 3000, "description", "Team retreat"));
            System.out.println("Execution started: " + exec.get("execution_id"));
            System.out.println("The workflow will pause at the approval step.");
            System.out.println("Approve via: jamjet executions approve <exec-id> --decision approved");
        } catch (Exception e) {
            System.out.println("Runtime not available — skipping submission.");
            System.out.println("Start the runtime with: jamjet dev");
        }
    }

    private static void printResult(ExpenseState state) {
        System.out.println("  Employee:  " + state.employeeName());
        System.out.printf("  Amount:    $%.2f (%s)%n", state.amount(), state.category());
        System.out.println("  Decision:  " + state.decision());
        System.out.println("  Notice:    " + state.notificationSent());
        System.out.println();
    }
}
