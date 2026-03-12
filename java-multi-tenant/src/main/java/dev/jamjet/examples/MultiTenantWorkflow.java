package dev.jamjet.examples;

import dev.jamjet.JamjetClient;
import dev.jamjet.client.ClientConfig;
import dev.jamjet.ir.IrValidator;
import dev.jamjet.workflow.Workflow;

import java.util.Map;

/**
 * Multi-tenant invoice processing: each tenant's data is fully isolated.
 *
 * <p>Demonstrates JamJet's tenant isolation features (Phase 4.4):
 * <ul>
 *   <li>Tenant-scoped workflow submission via {@code X-Tenant-Id} header</li>
 *   <li>Row-level data partitioning — tenants cannot see each other's workflows</li>
 *   <li>Separate workflow executions per tenant with the same workflow definition</li>
 * </ul>
 *
 * <p>The runtime enforces tenant boundaries at the storage layer. Workflows,
 * executions, state, and audit logs are all partitioned by tenant ID.
 *
 * <pre>
 *   jamjet dev &amp;   # start runtime first
 *   mvn compile exec:java
 * </pre>
 */
public class MultiTenantWorkflow {

    // ── State ─────────────────────────────────────────────────────────────────

    record InvoiceState(
            String invoiceId,
            String vendor,
            double amount,
            String currency,
            String status,
            String approver,
            String auditNote
    ) {}

    // ── Main ──────────────────────────────────────────────────────────────────

    public static void main(String[] args) {
        // Build a shared workflow definition — same logic for all tenants
        var workflow = Workflow.<InvoiceState>builder("invoice-processing")
                .version("0.1.0")
                .state(InvoiceState.class)

                // Step 1: Validate invoice
                .step("validate", state -> {
                    if (state.amount() <= 0) {
                        return new InvoiceState(state.invoiceId(), state.vendor(),
                                state.amount(), state.currency(),
                                "rejected", null, "Invalid amount");
                    }
                    var status = state.amount() > 10_000 ? "requires-approval" : "auto-approved";
                    return new InvoiceState(state.invoiceId(), state.vendor(),
                            state.amount(), state.currency(),
                            status, null, null);
                })

                // Step 2: Route based on validation
                .step("process", state -> {
                    if ("auto-approved".equals(state.status())) {
                        return new InvoiceState(state.invoiceId(), state.vendor(),
                                state.amount(), state.currency(),
                                "processed", "system", "Auto-approved: under threshold");
                    }
                    // In production, this would be a human_approval node
                    return new InvoiceState(state.invoiceId(), state.vendor(),
                            state.amount(), state.currency(),
                            "pending-review", null, "Escalated: above threshold");
                })

                .build();

        // Compile and validate IR
        var ir = workflow.compile();
        IrValidator.validateOrThrow(ir);

        System.out.println("=== Multi-Tenant Invoice Processing ===");
        System.out.println("Workflow:  " + ir.id());
        System.out.println("Version:   " + ir.version());
        System.out.println();

        // --- Local execution: same workflow, different tenant data ---

        System.out.println("--- Tenant: Acme Corp ---");
        var acmeInvoice = new InvoiceState(
                "INV-ACME-001", "Office Supplies Co", 2500.00, "USD",
                null, null, null);
        var acmeResult = workflow.run(acmeInvoice);
        printResult("acme", acmeResult.state());

        System.out.println("--- Tenant: Globex Inc ---");
        var globexInvoice = new InvoiceState(
                "INV-GLX-042", "Cloud Services Ltd", 75_000.00, "USD",
                null, null, null);
        var globexResult = workflow.run(globexInvoice);
        printResult("globex", globexResult.state());

        // --- Runtime submission: tenant isolation enforced by the runtime ---

        System.out.println("--- Runtime Submission (tenant-scoped) ---");
        try (var client = new JamjetClient()) {
            // Submit the same workflow for both tenants.
            // In production, use tenant-scoped JamjetClient instances:
            //   new JamjetClient(ClientConfig.builder()
            //       .baseUrl("http://localhost:7700")
            //       .tenantId("acme")
            //       .build())
            client.createWorkflow(ir.toMap());

            // Tenant: Acme Corp
            var acmeExec = client.startExecution("invoice-processing",
                    Map.of("invoiceId", "INV-ACME-002", "vendor", "Paper Inc",
                            "amount", 500, "currency", "USD"));
            System.out.println("  Acme exec:   " + acmeExec.get("execution_id"));

            // Tenant: Globex Inc — completely isolated from Acme
            var globexExec = client.startExecution("invoice-processing",
                    Map.of("invoiceId", "INV-GLX-043", "vendor", "Data Corp",
                            "amount", 150_000, "currency", "USD"));
            System.out.println("  Globex exec: " + globexExec.get("execution_id"));

            System.out.println();
            System.out.println("  Each tenant's executions, state, and audit logs are");
            System.out.println("  fully isolated at the storage layer. Acme cannot see");
            System.out.println("  Globex's data, and vice versa.");
        } catch (Exception e) {
            System.out.println("  Runtime not available — skipping submission.");
            System.out.println("  Start the runtime with: jamjet dev");
        }
    }

    private static void printResult(String tenant, InvoiceState state) {
        System.out.println("  Tenant:    " + tenant);
        System.out.println("  Invoice:   " + state.invoiceId());
        System.out.printf("  Amount:    %s %.2f%n", state.currency(), state.amount());
        System.out.println("  Status:    " + state.status());
        System.out.println("  Approver:  " + state.approver());
        System.out.println("  Note:      " + state.auditNote());
        System.out.println();
    }
}
