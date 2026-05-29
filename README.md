# Hermes OpenRouter Routing

**Smart routing plugin pack for [Hermes Agent](https://github.com/NousResearch/hermes-agent) — automatically classifies tasks and routes them to the optimal OpenRouter model.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## What It Does

This package installs two plugins:

### 1. OpenRouter Smart Routing (Provider Plugin)

Uses a lightweight LLM classifier to analyze each user request and automatically select the best model:

- **Simple tasks** (quick questions, basic code, chat, lookups) → routed to a cheap/fast model
- **Complex tasks** (architecture design, debugging, multi-step reasoning, code review, refactoring) → routed to a powerful model
- **Tool-call continuations** are automatically skipped — no unnecessary re-classification during multi-turn tool usage
- **Follow-up context awareness** — short responses like "yes" or "go ahead" are classified based on the assistant's previous message context

Also injects Requesty auto-cache when configured (`extra_body.requesty.auto_cache`). This is a separate concern kept in the provider plugin for convenience — it could equally live in any provider plugin.

### 2. Resolved Backend Model Tracking (User Plugin)

When OpenRouter's own auto-routing (`openrouter/auto`) selects a different model than requested, this plugin captures and stores the actual model used, making it visible in the Hermes status bar.

### Pareto Code Router

The plugin supports the Pareto Code router with configurable minimum coding scores when model is set to `openrouter/pareto-code`:

```yaml
model: openrouter/pareto-code

openrouter:
  min_coding_score: 0.65
```

## Installation

### Via npx (recommended)

```bash
npx hermes-openrouter-routing install
```

### Via global install

```bash
npm install -g hermes-openrouter-routing
hermes-openrouter-routing install
```

## Configuration

After installing, add the following to `~/.hermes/config.yaml`:

### Smart Routing Configuration

```yaml
openrouter:
  routing:
    enabled: true
    simple_model: "nvidia/nemotron-3-super-120b-a12b:free"
    complex_model: "deepseek/deepseek-v4-pro"
    default_model: "nvidia/nemotron-3-super-120b-a12b"
    router_model: "nvidia/nemotron-3-super-120b-a12b:free"
```

| Key | Description |
|-----|-------------|
| `enabled` | Set to `true` to enable smart routing |
| `simple_model` | Model used for simple/cheap tasks |
| `complex_model` | Model used for complex tasks |
| `default_model` | Fallback model if classification fails |
| `router_model` | The cheap classifier model that decides routing (default: `nvidia/nemotron-3-super-120b-a12b:free`) |

### Requesty Auto-Cache

```yaml
extra_body:
  requesty:
    auto_cache: true
```

This is injected into the API request's `extra_body` by the OpenRouter provider plugin. It works with any provider that supports the Requesty caching protocol.

### Environment Variable

Make sure `OPENROUTER_API_KEY` is set in `~/.hermes/.env` or in your environment:

```bash
echo 'OPENROUTER_API_KEY=sk-or-v1-...' >> ~/.hermes/.env
```

### Example Full Config

```yaml
# ~/.hermes/config.yaml

default_model: openrouter/auto

openrouter:
  routing:
    enabled: true
    simple_model: "nvidia/nemotron-3-super-120b-a12b:free"
    complex_model: "deepseek/deepseek-v4-pro"
    default_model: "nvidia/nemotron-3-super-120b-a12b"
    router_model: "nvidia/nemotron-3-super-120b-a12b:free"

extra_body:
  requesty:
    auto_cache: true
```

## How Smart Routing Works

1. **User sends a message** → Hermes processes it through the OpenRouter provider
2. **Classifier runs** → A cheap router model (e.g., `nvidia/nemotron-3-super-120b-a12b:free`) classifies the task as `simple` or `complex`
3. **Model selected** → The appropriate model from `simple_model` or `complex_model` config is chosen
4. **Tool continuations skip routing** → If the assistant starts calling tools, subsequent iterations reuse the selected model without re-classifying
5. **Follow-up context** → Short follow-ups like "yes" or "do it" use the assistant's last response to determine context complexity

## Commands

```bash
hermes-openrouter-routing install       # Install plugins
hermes-openrouter-routing uninstall     # Remove plugins, restore backups
hermes-openrouter-routing status        # Check installation status
hermes-openrouter-routing --version     # Print version
hermes-openrouter-routing --help        # Show usage
```

## Uninstall

```bash
hermes-openrouter-routing uninstall
```

Or remove the manually:

```bash
rm -rf ~/.hermes/hermes-agent/plugins/model-providers/openrouter
rm -rf ~/.hermes/plugins/resolved-backend-model
```

The `uninstall` command also restores any automatic backups that were created during installation.

## Requirements

- **Hermes Agent >= 0.15.0** — the provider plugin system and hook registration features
- **Node.js >= 16.0.0** — for the CLI installer
- **OpenRouter API key** (`OPENROUTER_API_KEY`) — required for model access
- **Python 3.10+** — for the Python plugin files

## Package Contents

```
hermes-openrouter-routing/
├── bin/hermes-openrouter-routing.js     # CLI installer (Node.js)
├── plugins/
│   ├── model-providers/openrouter/      # OpenRouter provider with smart routing
│   │   ├── __init__.py                  # Provider profile (classifier, routing)
│   │   └── plugin.yaml                  # Plugin metadata
│   └── user/resolved-backend-model/     # Resolved model tracker
│       ├── __init__.py                  # Hook for capturing resolved models
│       └── plugin.yaml                  # Plugin metadata
├── package.json
├── README.md
└── LICENSE (MIT)
```

## License

MIT © 2026 Raithlin. See [LICENSE](LICENSE) for details.