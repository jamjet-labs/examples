# Vertex AI + JamJet

Run JamJet agents powered by **Gemini on Vertex AI**. Vertex AI exposes an OpenAI-compatible endpoint, so JamJet works with it out of the box — no custom integration needed.

This example: a two-step research agent that plans sub-questions with Gemini Flash, then synthesizes a full report with Gemini Pro.

## Prerequisites

1. A Google Cloud project with the Vertex AI API enabled
2. `gcloud` CLI installed and authenticated
3. JamJet installed

```bash
pip install jamjet
gcloud auth application-default login
```

## Setup

```bash
export VERTEX_PROJECT=your-gcp-project-id
export VERTEX_LOCATION=us-central1          # change to your preferred region
```

JamJet (and the OpenAI SDK underneath) reads `OPENAI_BASE_URL` and `OPENAI_API_KEY`.
Set them from your Vertex AI project:

```bash
export OPENAI_BASE_URL="https://${VERTEX_LOCATION}-aiplatform.googleapis.com/v1beta1/projects/${VERTEX_PROJECT}/locations/${VERTEX_LOCATION}/endpoints/openapi"
export OPENAI_API_KEY=$(gcloud auth print-access-token)
```

> **Note:** Access tokens expire after 1 hour. For production, use the `google-auth` library
> to refresh automatically — see [Token refresh in production](#token-refresh-in-production) below.

## Run — simple Python (no JamJet)

Start here if you just want to hit Vertex AI with the OpenAI SDK directly:

```bash
python simple.py
```

Shows two approaches:
- **single call** — one prompt, one response, no tools
- **with tool** — manual tool loop with `current_date`

## Run — JamJet @task/@tool

Compare `simple.py` with this to see what JamJet removes:

```bash
python workflow.py
```

## Run — YAML workflow (requires `jamjet dev`)

```bash
jamjet dev &   # start the local runtime

jamjet run workflow.yaml \
  --input '{"query": "What are the key trends in AI agents in 2025?"}'
```

## Available Gemini models

| Model string | Notes |
|---|---|
| `google/gemini-2.0-flash-001` | Fast, cost-efficient |
| `google/gemini-2.0-pro-exp-02-05` | Most capable |
| `google/gemini-1.5-pro-002` | Long context (2M tokens) |
| `google/gemini-1.5-flash-002` | Fast + long context |

Use the model string directly in `workflow.yaml` or `@task(model=...)`.

## Token refresh in production

For long-running services, refresh the token automatically using `google-auth`:

```python
import google.auth
import google.auth.transport.requests

credentials, project = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)

def get_access_token() -> str:
    credentials.refresh(google.auth.transport.requests.Request())
    return credentials.token
```

Or use a sidecar that writes a fresh token to `OPENAI_API_KEY` every 45 minutes.

## Run evals

```bash
jamjet eval run evals/dataset.jsonl \
  --workflow workflow.yaml \
  --rubric "Rate answer quality 1-5" \
  --fail-below 4
```

## What it demonstrates

- Using Vertex AI's OpenAI-compatible endpoint with zero custom integration
- Chaining two Gemini models (Flash for speed, Pro for quality)
- `@task` decorator — docstring becomes the agent's instruction
- YAML workflow authoring for the same logic
- How to handle Vertex AI auth in dev vs production
