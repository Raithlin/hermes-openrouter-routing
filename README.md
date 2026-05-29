# Hermes OpenRouter Routing

**Smart routing plugin pack for [Hermes Agent](https://github.com/NousResearch/hermes-agent) — automatically classifies tasks and routes them to the optimal OpenRouter model.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## What It Does

This package installs two plugins that work together to make OpenRouter usage smarter and more cost-effective:

### 1. Smart Routing (OpenRouter Provider Plugin)

Uses a lightweight LLM classifier to analyze each user request and automatically select the best model:

- **Simple tasks** (quick questions, basic code, chat, lookups) → routed to a cheap/fast model like `nvidia/nemotron-3-super-120b-a12b:free`
- **Complex tasks** (architecture design, debugging, multi-step reasoning, code review, refactoring) → routed to a powerful model like `deepseek/deepseek-v4-pro`
- **Tool-call continuations** are automatically skipped — no unnecessary re-classification during multi-turn tool usage
- **Follow-up context awareness** — short responses like "yes" or "go ahead" are classified based on the assistant's previous message context

### 2. Requesty Auto-Cache

Enables auto-caching for Requesty providers to reduce latency and cost on repeated queries.

### 3. Resolved Backend Model Tracking

When OpenRouter's own auto-routing (`openrouter/auto`) selects a different model than requested, this plugin captures and stores the actual model used, making it visible in the Hermes status bar.

### 4. Provider Preferences & Pareto Code

Passes through provider preferences and supports the Pareto Code router (`openrouter/pareto-code`) with configurable minimum coding scores.

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

### Auto-Cache Configuration

```yaml
extra_body:
  requesty:
    auto_cache: true
```

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