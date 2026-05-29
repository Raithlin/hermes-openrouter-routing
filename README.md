# Hermes Task Router

**Provider-agnostic smart task routing for Hermes** — uses an LLM classifier to route simple tasks to fast/cheap models and complex tasks to powerful models. Works with [OpenRouter](https://openrouter.ai), [Requesty](https://requesty.ai), or any Hermes provider.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## What It Does

### Smart Task Routing

Every new user message is classified as "simple" or "complex" by a cheap router model:

- **Simple tasks** (quick questions, basic code, chat, lookups) → routed to your `simple_model`
- **Complex tasks** (architecture design, debugging, multi-step reasoning, code review) → routed to your `complex_model`
- **Tool-call continuations** skip routing — no unnecessary re-classification during multi-turn tool usage
- **Follow-up context awareness** — short responses like "yes" or "go ahead" use the assistant's previous message for classification context

### Requesty Auto-Cache

Enables `auto_cache` for Requesty providers to reduce latency on repeated queries.

### Resolved Backend Model Tracking

When a provider's auto-routing selects a different model than requested, the actual model used is captured and stored for display in the status bar.

## Installation

```bash
npx hermes-task-router install
```

Or globally:

```bash
npm install -g hermes-task-router
hermes-task-router install
```

Then add the required configuration (see below) and restart the gateway:

```bash
hermes gateway restart
```

## Configuration

All configuration lives in `~/.hermes/config.yaml`.

### Required: Smart Routing

```yaml
openrouter:          # Or your provider's config block
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

To use OpenRouter's built-in auto-router instead of the local classifier, set `model: openrouter/auto`. Local smart routing is automatically skipped.

```yaml
model: openrouter/auto

provider_preferences:
  plugins:
    - id: auto-router
      allowed_models:
        - nvidia/nemotron-3-super-120b:a12b:free
        - deepseek/deepseek-v4-flash
        - deepseek/deepseek-v4-pro
        - anthropic/claude-sonnet-4
```

### Optional: Pareto Code Router

When model is set to `openrouter/pareto-code`:

```yaml
model: openrouter/pareto-code

openrouter:
  min_coding_score: 0.65
```

## How It Works

1. **User sends a message** → Hermes processes it through the provider
2. **Classifier runs** → A cheap router model classifies the task as `simple` or `complex`
3. **Model is selected** → The appropriate model from your config is chosen
4. **API call proceeds** → The selected model handles the request
5. **Tool continuations skip** → Multi-tool sessions keep the selected model without re-classifying

On classification failure (network error, timeout, unexpected response), the current model is kept and the failure is logged at debug level.

## Requirements

- **Hermes Agent >= 0.15.0**
- **OpenRouter API key** (`OPENROUTER_API_KEY` env var, for smart routing classifier)
- **Node.js >= 16.0.0** (for the CLI installer)

## Commands

```bash
hermes-task-router install       # Install plugins (backs up existing files)
hermes-task-router uninstall     # Remove plugins, restore backups
hermes-task-router status        # Check installation status
hermes-task-router --version     # Print version
hermes-task-router --help        # Show usage
```

## Compatibility

Zero core files are modified. The plugin overrides the bundled OpenRouter provider by living at the canonical path:

```
~/.hermes/hermes-agent/plugins/model-providers/openrouter/__init__.py
```

Survives `hermes update` as long as upstream doesn't change the `ProviderProfile` base class method signatures.

## License

MIT © 2026 Raithlin. See [LICENSE](LICENSE) for details.
