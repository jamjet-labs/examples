package dev.jamjet.examples;

import dev.jamjet.ir.IrValidator;
import dev.jamjet.workflow.Workflow;

import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * PII-aware customer onboarding with data governance policies.
 *
 * <p>Demonstrates JamJet's enterprise data governance features (Phase 4.6–4.7):
 * <ul>
 *   <li>PII detection — regex-based patterns for email, SSN, phone, credit card</li>
 *   <li>PII redaction — mask, hash, or remove sensitive fields before storage</li>
 *   <li>Data retention — configurable retention periods with automatic purge</li>
 *   <li>Audit trail — redacted entries with full provenance tracking</li>
 * </ul>
 *
 * <p>When submitted to the runtime, the data policy in the workflow IR controls
 * how the PII redaction engine processes state at each step. Prompts and outputs
 * can be stripped from audit logs based on retention policy.
 *
 * <pre>
 *   mvn compile exec:java
 * </pre>
 */
public class DataGovernanceWorkflow {

    // ── PII patterns (same as runtime's built-in detectors) ──────────────────

    private static final Pattern EMAIL = Pattern.compile(
            "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}");
    private static final Pattern SSN = Pattern.compile(
            "\\b\\d{3}-\\d{2}-\\d{4}\\b");
    private static final Pattern PHONE = Pattern.compile(
            "\\b\\d{3}[-.\\s]?\\d{3}[-.\\s]?\\d{4}\\b");
    private static final Pattern CREDIT_CARD = Pattern.compile(
            "\\b\\d{4}[- ]?\\d{4}[- ]?\\d{4}[- ]?\\d{4}\\b");

    // ── State ─────────────────────────────────────────────────────────────────

    record OnboardingState(
            String customerId,
            String fullName,
            String email,
            String phone,
            String ssn,
            String creditCard,
            String kycStatus,
            String redactedSummary,
            List<String> piiFieldsDetected,
            int retentionDays
    ) {}

    // ── Main ──────────────────────────────────────────────────────────────────

    public static void main(String[] args) {
        var workflow = Workflow.<OnboardingState>builder("customer-onboarding")
                .version("0.1.0")
                .state(OnboardingState.class)

                // Step 1: Detect PII in the input
                .step("detect_pii", state -> {
                    var detected = new java.util.ArrayList<String>();
                    if (state.email() != null && EMAIL.matcher(state.email()).find())
                        detected.add("email");
                    if (state.ssn() != null && SSN.matcher(state.ssn()).find())
                        detected.add("ssn");
                    if (state.phone() != null && PHONE.matcher(state.phone()).find())
                        detected.add("phone");
                    if (state.creditCard() != null && CREDIT_CARD.matcher(state.creditCard()).find())
                        detected.add("credit_card");

                    return new OnboardingState(
                            state.customerId(), state.fullName(),
                            state.email(), state.phone(), state.ssn(), state.creditCard(),
                            "pii-detected", null, detected, 90);
                })

                // Step 2: KYC verification (uses PII, then redacts)
                .step("kyc_verify", state -> {
                    // In production, call a KYC API with the real SSN/ID
                    var kycResult = state.ssn() != null ? "verified" : "manual-review";

                    return new OnboardingState(
                            state.customerId(), state.fullName(),
                            state.email(), state.phone(), state.ssn(), state.creditCard(),
                            kycResult, null, state.piiFieldsDetected(), state.retentionDays());
                })

                // Step 3: Redact PII and produce safe summary
                .step("redact_and_store", state -> {
                    // Mask PII fields (the runtime does this automatically via DataPolicyIr)
                    var maskedEmail = mask(state.email(), EMAIL);
                    var maskedPhone = mask(state.phone(), PHONE);
                    var maskedSsn = state.ssn() != null ? "***-**-" + state.ssn().substring(7) : null;
                    var maskedCard = state.creditCard() != null
                            ? "****-****-****-" + state.creditCard().substring(state.creditCard().length() - 4)
                            : null;

                    var summary = """
                            Customer: %s (ID: %s)
                            Email:    %s
                            Phone:    %s
                            SSN:      %s
                            Card:     %s
                            KYC:      %s
                            PII fields detected: %s
                            Retention: %d days""".formatted(
                            state.fullName(), state.customerId(),
                            maskedEmail, maskedPhone, maskedSsn, maskedCard,
                            state.kycStatus(),
                            String.join(", ", state.piiFieldsDetected()),
                            state.retentionDays());

                    return new OnboardingState(
                            state.customerId(), state.fullName(),
                            maskedEmail, maskedPhone, maskedSsn, maskedCard,
                            state.kycStatus(), summary,
                            state.piiFieldsDetected(), state.retentionDays());
                })

                .build();

        // Compile and validate
        var ir = workflow.compile();
        IrValidator.validateOrThrow(ir);

        System.out.println("=== Data Governance: PII-Aware Customer Onboarding ===");
        System.out.println("Workflow:  " + ir.id());
        System.out.println("Version:   " + ir.version());
        System.out.println("Nodes:     " + ir.nodes().size());
        System.out.println();

        // Simulate onboarding with PII
        var input = new OnboardingState(
                "CUST-7291", "Jane Doe",
                "jane.doe@example.com", "555-123-4567",
                "123-45-6789", "4111-1111-1111-1234",
                null, null, List.of(), 0);

        System.out.println("--- Input (contains PII) ---");
        System.out.println("  Name:   " + input.fullName());
        System.out.println("  Email:  " + input.email());
        System.out.println("  Phone:  " + input.phone());
        System.out.println("  SSN:    " + input.ssn());
        System.out.println("  Card:   " + input.creditCard());
        System.out.println();

        var result = workflow.run(input);
        var state = result.state();

        System.out.println("--- Output (PII redacted) ---");
        System.out.println("  PII fields detected: " + state.piiFieldsDetected());
        System.out.println("  KYC status: " + state.kycStatus());
        System.out.println("  Retention:  " + state.retentionDays() + " days");
        System.out.println();
        System.out.println("=== Redacted Summary (safe for audit log) ===");
        System.out.println(state.redactedSummary());
        System.out.println();
        System.out.println("--- Runtime Data Policy ---");
        System.out.println("  When submitted to the JamJet runtime, the DataPolicyIr");
        System.out.println("  in the workflow IR controls automatic PII redaction:");
        System.out.println("    - pii_detectors: email, ssn, phone, credit_card");
        System.out.println("    - redaction_mode: mask (or hash, remove)");
        System.out.println("    - retain_prompts: false");
        System.out.println("    - retain_outputs: false");
        System.out.println("    - retention_days: 90");
        System.out.println("  Audit entries auto-expire after the retention period.");
    }

    private static String mask(String value, Pattern pattern) {
        if (value == null) return null;
        return pattern.matcher(value).replaceAll(m -> {
            var match = m.group();
            if (match.length() <= 4) return "****";
            return "*".repeat(match.length() - 4) + match.substring(match.length() - 4);
        });
    }
}
