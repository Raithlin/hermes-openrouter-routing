# Hermes OpenRouter Routing

**Smart routing plugin for OpenRouter on Hermes** — uses an LLM classifier to route simple tasks to fast/cheap models and complex tasks to powerful models. Also injects Requesty auto-cache when configured, and tracks the resolved backend model from OpenRouter auto-routing.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## What It Does

### OpenRouter Smart Routing

When OpenRouter is your active provider, every new user message is classified as "simple" or "complex" by a cheap router model:

- **Simple tasks** (quick questions, basic code, chat, lookups) → routed to your `simple_model`
- **Complex tasks** (architecture design, debugging, multi-step reasoning, code review) → routed to your `complex_model`
- **Tool-call continuations** skip routing — no unnecessary re-classification during multi-turn tool usage
- **Follow-up context awareness** — short responses like "yes" or "go ahead" use the assistant's previous message for classification context

### Requesty Auto-Cache

Injects `requesty.auto_cache: true` into `extra_body` when configured. This is a separate concern bundled here for convenience — it's provider-agnostic but lives in this plugin because OpenRouter is the primary use case.

### Resolved Backend Model Tracking

When OpenRouter's auto-routing (`openrouter/auto`) selects a different model than requested, the actual model used is captured and stored for display in the status bar.

### Pareto Code Router

When model is set to `openrouter/pareto-code`, a `pareto-router` plugin with configurable `min_coding_score` is injected into `extra_body`.

## Installation

```bash
npx hermes-openrouter-routing install
```

Or globally:

```bash
npm install -g hermes-openrouter-routing
hermes-openrouter-routing install
```

Then add the required configuration (see below) and restart Hermes:

```bash
hermes gateway restart
```

## Configuration

All configuration lives in `~/.hermes/config.yaml`.

### Required: Smart Routing

```yaml
openrouter:
  routing:
    enabled: true
    simple_model: "nvidia/nemotron-3-super-120b-a12b:free"
    complex_model: "deepseek/deepseek-v4-pro"
    default_model: "nvidia/nemotron-3-super-120b:a12b"
    router_model: "nvidia/nemotron-3-super-120b-a12b:free"
```

| Key | Required | Description |
|-----|----------|-------------|
| `enabled` | Yes | Enable smart routing |
| `simple_model` | Yes | Model for simple/cheap tasks |
| `complex_model` | Yes | Model for complex tasks |
| `default_model` | No | Fallback if classification fails |
| `router_model` | No | Classifier model (default: `nvidia/nemotron-3-super-120b-a12b:free`) |

### Optional: Requesty Auto-Cache

```yaml
extra_body:
  requesty:
    auto_cache: true
```

### Optional: OpenRouter Auto-Router (NotDiamond)

To use OpenRouter's built-in auto-router instead of the local classifier, set `model: openrouter/auto`. Local smart routing is automatically skipped:

```yaml
model: openrouter/auto
```

### Optional: Pareto Code Router

```yaml
model: openrouter/pareto-code

openrouter:
  min_coding_score: 0.65
```

## Requirements

- **Hermes Agent >= 0.15.0**
- **OpenRouter API key** (`OPENROUTER_API_KEY` env var, for the smart routing classifier)
- **Node.js >= 16.0.0** (for the CLI installer)

## Scope

This plugin only runs when OpenRouter is the active provider. If you use Requesty or another provider, a separate plugin would be needed for each provider.

## Commands

```bash
hermes-openrouter-routing install       # Install plugins (backs up existing files)
hermes-openrouter-routing uninstall     # Remove plugins, restore backups
hermes-openrouter-routing status        # Check installation status
hermes-openrouter-routing --version     # Print version
hermes-openrouter-routing --help        # Show usage
```

## Compatibility

Zero core files are modified. The plugin overrides the bundled OpenRouter provider at its canonical path:

```
~/.hermes/hermes-agent/plugins/model-providers/openrouter/__init__.py
```

Survives `hermes update` as long as upstream doesn't change the `ProviderProfile` base class method signatures (`prepare_messages`, `build_extra_body`, `build_api_kwargs_extras`).

## License

MIT © 2026 Raithlin. See [LICENSE](LICENSE) for details.
