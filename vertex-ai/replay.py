"""Replays benchmark_output.txt with realistic line delays for recording."""
import sys, time

delays = {
    "Planning": 0.4,
    "Synthesizing": 0.4,
    "✓ completed": 0.2,
    "METRICS": 0.1,
    "REPORT": 0.1,
    "Benchmark complete": 0.3,
    "==": 0.05,
    "──": 0.03,
    "  Step": 0.05,
    "  plan": 0.15,
    "  synth": 0.15,
    "  call_": 0.08,
    "  TOTAL": 0.1,
    "  Estimated": 0.12,
    "  Wall": 0.1,
    "  API": 0.1,
}

with open("benchmark_output.txt") as f:
    lines = f.readlines()

for line in lines:
    sys.stdout.write(line)
    sys.stdout.flush()
    stripped = line.strip()
    delay = 0.04
    for key, d in delays.items():
        if stripped.startswith(key) or key in stripped:
            delay = d
            break
    # Extra pause before big sections
    if "▶ Step 2" in line:
        time.sleep(0.6)
    time.sleep(delay)
