package dev.jamjet.examples;

import dev.jamjet.ir.IrValidator;
import dev.jamjet.workflow.Workflow;

/**
 * Three-step support ticket workflow: classify, search KB, draft reply.
 *
 * <p>Java equivalent of the {@code support-bot/} Python SDK example.
 * Demonstrates the Workflow builder API with conditional routing.
 *
 * <pre>
 *   mvn compile exec:java
 * </pre>
 */
public class SupportBot {

    // ── State ─────────────────────────────────────────────────────────────────

    record TicketState(
            String ticket,
            String ticketId,
            String category,
            String priority,
            String sentiment,
            String kbResults,
            String reply
    ) {}

    // ── Main ──────────────────────────────────────────────────────────────────

    public static void main(String[] args) {
        var workflow = Workflow.<TicketState>builder("support-bot")
                .version("0.1.0")
                .state(TicketState.class)

                // Step 1: Classify the ticket
                .step("classify", state -> {
                    // In production, call an LLM to classify
                    var ticket = state.ticket().toLowerCase();
                    String category;
                    String priority;
                    String sentiment;

                    if (ticket.contains("password") || ticket.contains("login") || ticket.contains("account")) {
                        category = "account";
                        priority = "high";
                    } else if (ticket.contains("bill") || ticket.contains("charge") || ticket.contains("refund")) {
                        category = "billing";
                        priority = "normal";
                    } else if (ticket.contains("crash") || ticket.contains("error") || ticket.contains("bug")) {
                        category = "technical";
                        priority = "urgent";
                    } else {
                        category = "other";
                        priority = "normal";
                    }

                    sentiment = ticket.contains("!") || ticket.contains("frustrated") || ticket.contains("angry")
                            ? "frustrated" : "neutral";

                    return new TicketState(state.ticket(), state.ticketId(),
                            category, priority, sentiment, null, null);
                })

                // Step 2: Search knowledge base
                .step("search_kb", state -> {
                    // In production, call a vector DB or search API
                    var results = switch (state.category()) {
                        case "account" -> """
                                KB-101: Password Reset Guide
                                - Go to Settings > Security > Reset Password
                                - Click "Forgot Password" on the login page
                                - Check spam folder for reset email
                                """;
                        case "billing" -> """
                                KB-201: Billing FAQ
                                - Refunds processed within 5-7 business days
                                - Contact billing@example.com for disputes
                                """;
                        case "technical" -> """
                                KB-301: Common Error Fixes
                                - Clear browser cache and cookies
                                - Try incognito/private browsing mode
                                - Check status.example.com for outages
                                """;
                        default -> "KB-001: General Help — Contact support@example.com";
                    };
                    return new TicketState(state.ticket(), state.ticketId(),
                            state.category(), state.priority(), state.sentiment(),
                            results, null);
                })

                // Step 3: Draft reply
                .step("draft_reply", state -> {
                    // In production, call an LLM with KB context
                    var empathy = state.sentiment().equals("frustrated")
                            ? "I completely understand how frustrating this must be. "
                            : "Thank you for reaching out. ";

                    var reply = """
                            Hi there,

                            %sI've looked into your ticket (%s) about: %s

                            Based on our knowledge base, here's how to resolve this:

                            %s

                            If this doesn't resolve your issue, please reply and we'll escalate to our specialist team.

                            Best regards,
                            The Support Team""".formatted(
                            empathy, state.ticketId(), state.category(), state.kbResults());

                    return new TicketState(state.ticket(), state.ticketId(),
                            state.category(), state.priority(), state.sentiment(),
                            state.kbResults(), reply);
                })

                .build();

        // Validate compiled IR
        var ir = workflow.compile();
        IrValidator.validateOrThrow(ir);

        System.out.println("Workflow:   " + ir.id());
        System.out.println("Version:    " + ir.version());
        System.out.println("Nodes:      " + ir.nodes().size());
        System.out.println("Edges:      " + ir.edges().size());
        System.out.println();

        // Run locally — no runtime needed
        var input = new TicketState(
                "I cannot log in to my account — it says my password is wrong!",
                "TKT-4821",
                null, null, null, null, null);

        System.out.println("Ticket: " + input.ticket());
        System.out.println("Running workflow...");
        System.out.println();

        var result = workflow.run(input);
        var state = result.state();

        System.out.println("Category:  " + state.category());
        System.out.println("Priority:  " + state.priority());
        System.out.println("Sentiment: " + state.sentiment());
        System.out.println();
        System.out.println("=== Reply ===");
        System.out.println(state.reply());
    }
}
