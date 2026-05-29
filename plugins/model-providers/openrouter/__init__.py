"""OpenRouter provider profile — smart routing, provider preferences,
reasoning config passthrough, Pareto Code router, requesty auto-cache.

All configuration is read directly from ~/.hermes/config.yaml.
No core file modifications needed.

Smart routing (openrouter.routing config section):
  Uses a cheap LLM classifier to route simple tasks to a fast/cheap model
  and complex tasks to a powerful model. Tool-call continuations skip routing.

Requesty auto-cache (extra_body.requesty config section):
  Reads extra_body.requesty.auto_cache from config and injects into extra_body.

Config example:
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
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from pathlib import Path
from typing import Any

from providers import register_provider
from providers.base import ProviderProfile

logger = logging.getLogger(__name__)

_CACHE: list[str] | None = None

# ── Routing config cache ──────────────────────────────────────────────

_ROUTING_CONFIG: dict[str, Any] | None = None
_ROUTING_CONFIG_LOADED = False

_REQUESTY_CONFIG: dict[str, Any] | None = None
_REQUESTY_CONFIG_LOADED = False

_ROUTING_PROMPT = """\
Classify this task as exactly one word: "simple" or "complex".

Simple tasks: quick questions, basic code snippets, simple lookups,
  chat, small edits, explanations of known concepts.

Complex tasks: architecture design, debugging, multi-step reasoning,
  code review, system design, refactoring, security analysis,
  performance optimization, multi-file changes.

IMPORTANT: If the task is a short follow-up (e.g. "yes", "go ahead",
"do it", "ok"), use the assistant context to infer complexity. A "yes"
that approves a complex proposal IS complex. A "yes" to a simple
question IS simple.

User message:
{task}

Assistant context (the message the user is responding to):
{context}

Respond with ONLY the word "simple" or "complex"."""


def _load_yaml_config() -> dict[str, Any]:
    """Load ~/.hermes/config.yaml once, cached."""
    global _ROUTING_CONFIG_LOADED, _REQUESTY_CONFIG_LOADED
    cfg: dict[str, Any] = {}
    try:
        import yaml  # type: ignore[import-untyped]
        config_path = Path.home() / ".hermes" / "config.yaml"
        if config_path.exists():
            with open(config_path) as f:
                cfg = yaml.safe_load(f) or {}
    except Exception:
        cfg = {}

    if not _ROUTING_CONFIG_LOADED:
        _ROUTING_CONFIG_LOADED = True
        _ROUTING_CONFIG = (cfg.get("openrouter") or {}).get("routing") or {}
    if not _REQUESTY_CONFIG_LOADED:
        _REQUESTY_CONFIG_LOADED = True
        _REQUESTY_CONFIG = (cfg.get("extra_body") or {}).get("requesty") or {}

    return cfg


def _load_routing_config() -> dict[str, Any]:
    _load_yaml_config()
    return _ROUTING_CONFIG or {}


def _load_requesty_config() -> dict[str, Any]:
    _load_yaml_config()
    return _REQUESTY_CONFIG or {}


# ── Message helpers ────────────────────────────────────────────────────

def _is_new_user_task(messages: list) -> bool:
    """True if the last non-tool message is from the user."""
    for msg in reversed(messages):
        if isinstance(msg, dict):
            role = msg.get("role", "")
            if role == "user":
                return True
            if role == "tool":
                return False
    return False


def _extract_task(messages: list) -> str:
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = [
                    p.get("text", "")
                    for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                ]
                return " ".join(parts)
    return ""


def _get_last_assistant_message(messages: list) -> str:
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            content = msg.get("content", "")
            if isinstance(content, str):
                return content[:1500] + "..." if len(content) > 1500 else content
            if isinstance(content, list):
                parts = [
                    p.get("text", "")
                    for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                ]
                text = " ".join(parts)
                return text[:1500] + "..." if len(text) > 1500 else text
    return "(no previous assistant message)"


# ── Classification ─────────────────────────────────────────────────────

def _classify_task(messages: list, router_model: str, base_url: str) -> str | None:
    """Classify task complexity via a cheap router model. Returns 'simple'/'complex'/None."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return None

    task = _extract_task(messages)
    if not task:
        return None

    context = _get_last_assistant_message(messages)
    if len(task) > 2000:
        task = task[:2000] + "..."

    prompt = _ROUTING_PROMPT.format(task=task, context=context)

    payload = json.dumps({
        "model": router_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 10,
        "temperature": 0.0,
    }).encode()

    url = base_url.rstrip("/") + "/chat/completions"

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "hermes-cli/openrouter-smart-routing",
            },
        )
        with urllib.request.urlopen(req, timeout=8.0) as resp:
            data = json.loads(resp.read().decode())

        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
            .lower()
        )
        if "complex" in content:
            return "complex"
        if "simple" in content:
            return "simple"
        return None
    except Exception as exc:
        logger.debug("openrouter: classification failed: %s", exc)
        return None


# ── Provider profile ───────────────────────────────────────────────────

class OpenRouterProfile(ProviderProfile):
    """OpenRouter aggregator — smart routing, provider preferences,
    reasoning config passthrough, Pareto Code, requesty auto-cache.

    Zero core file changes: all config read from ~/.hermes/config.yaml,
    messages/base_url captured via prepare_messages/build_extra_body overrides.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._messages: list = []
        self._base_url: str = ""
        self._requesty_auto_cache: bool = False

    def prepare_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Capture messages for smart routing classification."""
        self._messages = messages
        return messages

    def build_extra_body(
        self, *, session_id: str | None = None, **context: Any
    ) -> dict[str, Any]:
        """Build extra_body with provider preferences, Pareto Code, requesty auto-cache."""
        body: dict[str, Any] = {}

        # Capture base_url for smart routing
        self._base_url = context.get("base_url", "")

        prefs = context.get("provider_preferences")
        if prefs and isinstance(prefs, dict):
            plugins = prefs.get("plugins")
            if plugins and isinstance(plugins, list):
                body["plugins"] = plugins
                prefs = {k: v for k, v in prefs.items() if k != "plugins"}
            if prefs:
                body["provider"] = prefs

        # Pareto Code router — model-gated
        model = context.get("model") or ""
        if model == "openrouter/pareto-code":
            score = context.get("openrouter_min_coding_score")
            if score is not None and score != "":
                try:
                    score_f = float(score)
                except (TypeError, ValueError):
                    score_f = None
                if score_f is not None and 0.0 <= score_f <= 1.0:
                    if "plugins" not in body:
                        body["plugins"] = []
                    body["plugins"].append(
                        {"id": "pareto-router", "min_coding_score": score_f}
                    )

        # Requesty auto-cache — read from config
        requesty_cfg = _load_requesty_config()
        if requesty_cfg.get("auto_cache"):
            body.setdefault("requesty", {})["auto_cache"] = True

        return body

    def build_api_kwargs_extras(
        self,
        *,
        reasoning_config: dict | None = None,
        supports_reasoning: bool = False,
        model: str | None = None,
        session_id: str | None = None,
        **context: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Build extra_body and top-level kwargs including per-task smart routing."""
        extra_body: dict[str, Any] = {}
        if supports_reasoning:
            if reasoning_config is not None:
                extra_body["reasoning"] = dict(reasoning_config)
            else:
                extra_body["reasoning"] = {"enabled": True, "effort": "medium"}

        extra_headers: dict[str, Any] = {}
        if session_id and model and model.startswith(
            ("x-ai/grok-", "xai/grok-")
        ):
            extra_headers["x-grok-conv-id"] = session_id

        top_level: dict[str, Any] = {}
        if extra_headers:
            top_level["extra_headers"] = extra_headers

        # Smart routing — classify every new user message
        if self._messages and self._base_url and model:
            if model != "openrouter/auto":
                routing_cfg = _load_routing_config()
                if routing_cfg.get("enabled"):
                    if _is_new_user_task(self._messages):
                        router_model = routing_cfg.get(
                            "router_model",
                            "nvidia/nemotron-3-super-120b-a12b:free",
                        )
                        complexity = _classify_task(
                            self._messages, router_model, self._base_url
                        )
                        default_model = routing_cfg.get("default_model", "")
                        if complexity == "complex":
                            selected = routing_cfg.get("complex_model") or default_model
                        elif complexity == "simple":
                            selected = routing_cfg.get("simple_model") or default_model
                        else:
                            selected = ""

                        if selected and selected != model:
                            logger.info(
                                "openrouter smart routing: %s → %s (%s)",
                                model, selected, complex or "fallback",
                            )
                            top_level["model"] = selected

        return extra_body, top_level


openrouter = OpenRouterProfile(
    name="openrouter",
    aliases=("or",),
    env_vars=("OPENROUTER_API_KEY",),
    display_name="OpenRouter",
    description="OpenRouter — unified API for 300+ models with smart routing",
    signup_url="https://openrouter.ai/keys",
    base_url="https://openrouter.ai/api/v1",
    models_url="https://openrouter.ai/api/v1/models",
    fallback_models=(
        "anthropic/claude-sonnet-4.6",
        "openai/gpt-5.4",
        "deepseek/deepseek-chat",
        "google/gemini-3-flash-preview",
        "qwen/qwen3-plus",
    ),
)

register_provider(openrouter)