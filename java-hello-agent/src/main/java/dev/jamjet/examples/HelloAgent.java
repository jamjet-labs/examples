package dev.jamjet.examples;

import dev.jamjet.agent.Agent;
import dev.jamjet.ir.IrValidator;

/**
 * Minimal JamJet example — one agent, one question, one answer.
 *
 * <p>Java equivalent of the {@code hello-agent/} YAML example.
 *
 * <pre>
 *   export OPENAI_API_KEY=sk-...
 *   mvn compile exec:java
 * </pre>
 */
public class HelloAgent {

    public static void main(String[] args) {
        // Build a simple agent — no tools, just a model
        var agent = Agent.builder("hello-agent")
                .model("claude-haiku-4-5-20251001")
                .instructions("Answer questions clearly and concisely.")
                .strategy("react")
                .maxIterations(1)
                .build();

        // Compile to IR and validate
        var ir = agent.compile();
        var errors = IrValidator.validate(ir);
        if (!errors.isEmpty()) {
            System.err.println("IR validation failed:");
            errors.forEach(e -> System.err.println("  - " + e));
            System.exit(1);
        }

        System.out.println("Agent:      " + agent.name());
        System.out.println("Model:      " + agent.model());
        System.out.println("IR nodes:   " + ir.nodes().size());
        System.out.println("IR edges:   " + ir.edges().size());
        System.out.println();

        // Run the agent (requires OPENAI_API_KEY or OPENAI_BASE_URL)
        var apiKey = System.getenv("OPENAI_API_KEY");
        if (apiKey == null || apiKey.isBlank()) {
            System.out.println("OPENAI_API_KEY not set — printing IR only.");
            System.out.println(ir.toJson());
            return;
        }

        var query = args.length > 0 ? String.join(" ", args) : "What is JamJet?";
        System.out.println("Query: " + query);
        System.out.println();

        var result = agent.run(query);
        System.out.println(result.output());
    }
}
