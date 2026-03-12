package dev.jamjet.examples;

import dev.jamjet.agent.Agent;
import dev.jamjet.ir.IrValidator;
import dev.jamjet.tool.Tool;
import dev.jamjet.tool.ToolCall;

/**
 * Research agent with web search tool and plan-and-execute strategy.
 *
 * <p>Java equivalent of the {@code research-agent/} YAML example.
 * Demonstrates tool definition, registration, and multi-step reasoning.
 *
 * <pre>
 *   export OPENAI_API_KEY=sk-...
 *   mvn compile exec:java
 * </pre>
 */
public class ResearchAgent {

    // ── Tools ─────────────────────────────────────────────────────────────────

    @Tool(description = "Search the web for information. Returns relevant snippets.")
    record WebSearch(String query) implements ToolCall<String> {
        @Override
        public String execute() {
            // Stub — in production, call Brave Search, Serper, or SerpAPI
            return """
                    Search results for '%s':
                    1. JamJet is an agent-native runtime with MCP and A2A protocol support.
                    2. It uses durable graph-based workflow orchestration for reliability.
                    3. Agents are first-class runtime entities with autonomy controls.
                    4. The Python and Java SDKs compile to identical canonical IR.
                    5. Enterprise features include policy engines, audit logs, and budget enforcement.
                    """.formatted(query);
        }
    }

    @Tool(description = "Fetch the full text content of a web page by URL")
    record FetchPage(String url) implements ToolCall<String> {
        @Override
        public String execute() {
            // Stub — in production, use an HTTP client or headless browser
            return "Page content for " + url + ": [full article text would appear here]";
        }
    }

    // ── Main ──────────────────────────────────────────────────────────────────

    public static void main(String[] args) {
        var agent = Agent.builder("research-agent")
                .model("claude-sonnet-4-6")
                .tools(WebSearch.class, FetchPage.class)
                .instructions("""
                        You are a thorough research assistant. For any question:
                        1. Search the web for relevant information
                        2. Fetch important pages for detail
                        3. Synthesize a well-structured report with citations
                        """)
                .strategy("plan-and-execute")
                .maxIterations(8)
                .maxCostUsd(0.50)
                .build();

        // Validate compiled IR
        var ir = agent.compile();
        IrValidator.validateOrThrow(ir);

        System.out.println("Agent:      " + agent.name());
        System.out.println("Strategy:   " + agent.strategy());
        System.out.println("Tools:      " + agent.toolNames());
        System.out.println("Max iters:  " + agent.maxIterations());
        System.out.println("IR nodes:   " + ir.nodes().size());
        System.out.println();

        // Run
        var apiKey = System.getenv("OPENAI_API_KEY");
        if (apiKey == null || apiKey.isBlank()) {
            System.out.println("OPENAI_API_KEY not set — printing IR only.");
            System.out.println(ir.toJson());
            return;
        }

        var query = args.length > 0 ? String.join(" ", args) : "Compare AI agent frameworks in 2026";
        System.out.println("Query: " + query);
        System.out.println("Running plan-and-execute...");
        System.out.println();

        var result = agent.run(query);

        System.out.println("=== Report ===");
        System.out.println(result.output());
        System.out.println();
        System.out.printf("Tool calls: %d%n", result.toolCalls().size());
        System.out.printf("Duration:   %.1f ms%n", result.durationUs() / 1000.0);
    }
}
