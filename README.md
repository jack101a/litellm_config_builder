# LiteLLM Config Studio

A lightweight, local-first web UI for building, testing, linting, and exporting LiteLLM configs.

It is designed for people who manage many providers, many API keys, load-balanced deployments, NVIDIA NIM models, OpenRouter/Gemini/Groq/custom OpenAI-compatible endpoints, and LiteLLM WebUI imports.

## What it does

- Launches from terminal and chooses a free port automatically.
- Runs on `127.0.0.1` by default; LAN mode is opt-in.
- Generates LiteLLM `config.yaml` with explicit deployments, wildcard routes, or hybrid mode.
- Multiplies selected models across many API key env vars for load balancing.
- Fetches model lists where providers expose model APIs.
- Enriches NVIDIA models from `https://build.nvidia.com/{model_id}` pages.
- Extracts NVIDIA `extra_body.chat_template_kwargs` thinking/reasoning presets when visible in page/code snippets.
- Creates routing/retry/cooldown/health-check settings.
- Builds fallback chains.
- Provides live provider key/model smoke tests.
- Lints existing LiteLLM configs and flags common mistakes.
- Exports editable files and a zip bundle.

## Install locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Run:

```bash
litellm-config-studio
```

Optional LAN mode:

```bash
litellm-config-studio --lan
```

Optional fixed/preferred port:

```bash
litellm-config-studio --port 48731
```

If the requested port is busy, the launcher picks another free port.

## Generated files

The Output screen can generate:

- `config.yaml`
- `.env.example`
- `docker-compose.yml`
- `test-curl.sh`
- `litellm-import.py`
- `preflight-report.md`
- `models-report.json`

The `litellm-import.py` script can add generated models into a running LiteLLM proxy/WebUI database through `/model/new`.

## Security model

- The app binds to `127.0.0.1` by default.
- Real API keys are only used for live tests if pasted by the user.
- Generated config uses `os.environ/KEY_NAME` by default.
- Pasted keys are not written to output files.
- LAN mode is explicit because the UI may display sensitive data.

## NVIDIA notes

NVIDIA Build pages are webpages, not a stable metadata API. The Studio uses a conservative best-effort parser and labels metadata sources. Always live-test model-specific `extra_body` / thinking presets before production.

For NVIDIA hosted endpoints, explicit mode typically uses:

```yaml
litellm_params:
  model: openai/vendor/model-id
  api_base: https://integrate.api.nvidia.com/v1
  api_key: os.environ/NVIDIA_KEY_1
```

Hybrid mode can also create wildcard provider routes for experimentation.

## Development

```bash
pip install -e .
python -m compileall litellm_config_studio
litellm-config-studio --no-browser
```

This is a polished beta, still intentionally lightweight: FastAPI + Jinja2 + vanilla JavaScript, no database, no React build pipeline.
