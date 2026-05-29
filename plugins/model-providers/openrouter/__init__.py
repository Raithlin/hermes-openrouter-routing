"""OpenRouter provider profile — smart routing, provider preferences,
reasoning config passthrough, Pareto Code router.

Smart routing uses a cheap LLM classifier to route simple tasks to a fast/cheap
model and complex tasks to a powerful model. Tool-call continuations skip routing.
Config is read from ~/.hermes/config.yaml on each classification.

Also injects Requesty auto-cache when configured (extra_body.requesty.auto_cache).
This is a separate concern kept here for convenience — it could equally live in
any provider plugin or a standalone plugin.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from providers import register_provider
from providers.base import ProviderProfile

logger = logging.getLogger(__name__)

_CACHE: list[str] | None = None

# ── Config loading (not cached — re-read each time) ───────────────────

def _load_config_value(*keys: str) -> Any:
    """Read a nested value from ~/.hermes/config.yaml. Returns None on any error.

    Usage:
        _load_config_value("openrouter", "routing", "enabled")  # -> True/False/None
        _load_config_value("extra_body", "requesty", "auto_cache")
    """
    try:
        import yaml  # type: ignore[import-untyped]
        config_path = Path.home() / ".hermes" / "config.yaml"
        if not config_path.exists():
            return None
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}
        for key in keys:
            if not isinstance(cfg, dict):
                return None
            cfg = cfg.get(key)
            if cfg is None:
                return None
        return cfg
    except Exception:
        return None


def _get_routing_config() -> dict[str, Any]:
    val = _load_config_value("openrouter", "routing")
    return val if isinstance(val, dict) else {}


def _get_requesty_auto_cache() -> bool:
    return bool(_load_config_value("extra_body", "requesty", "auto_cache"))


# ── Message helpers ────────────────────────────────────────────────────

def _is_new_user_task(messages: list) -> bool:
    """True if the last non-tool message is from the user (new task, not a tool continuation)."""
    for msg in reversed(messages):
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "")
        if role == "user":
            return True
        if role == "tool":
            return False
    return False


def _extract_task(messages: list) -> str:
    """Extract the last user message content as a plain string."""
    for msg in reversed(messages):
        if not isinstance(msg, dict) or msg.get("role") != "user":
            continue
        content = msg.get("content")
        if content is None:
            continue
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text = part.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            if parts:
                return " ".join(parts)
    return ""


def _get_last_assistant_message(messages: list, max_chars: int = 1500) -> str:
    """Extract the last assistant message content for follow-up context."""
    for msg in reversed(messages):
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        content = msg.get("content")
        if content is None:
            continue
        if isinstance(content, str):
            return content[:max_chars] + "..." if len(content) > max_chars else content
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text = part.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            if parts:
                text = " ".join(parts)
                return text[:max_chars] + "..." if len(text) > max_chars else text
    return "(no previous assistant message)"


# ── Classification with retry ──────────────────────────────────────────

def _classify_task(
    messages: list,
    router_model: str,
    base_url: str,
    max_retries: int = 2,
    timeout: float = 10.0,
) -> str | None:
    """Classify task complexity via a cheap router model.

    Returns "simple" or "complex", or None if classification fails after retries.
    Includes retry logic for transient network errors.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return None

    task = _extract_task(messages)
    if not task:
        return None

    context = _get_last_assistant_message(messages)

    # Truncate long tasks — the classifier only needs the gist
    if len(task) > 2000:
        task = task[:2000] + "..."

    prompt = (
        f'Classify this task as exactly one word: "simple" or "complex".\n\n'
        f"Simple tasks: quick questions, basic code snippets, simple lookups, "
        f"chat, small edits.\n\n"
        f"Complex tasks: architecture design, debugging, multi-step reasoning, "
        f"code review, system design, refactoring, security analysis.\n\n"
        f'IMPORTANT: Short follow-ups ("yes", "go ahead", "ok") should be classified '
        f"based on the assistant context that follows.\n\n"
        f"User message:\n{task}\n\n"
        f"Assistant context:\n{context}\n\n"
        f'Respond with ONLY the word "simple" or "complex".'
    )

    payload = json.dumps({
        "model": router_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 10,
        "temperature": 0.0,
    }).encode()

    url = base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "hermes-cli/openrouter-smart-routing",
    }

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=payload, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
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

            logger.debug("openrouter: unexpected classification response: %r", content)
            return None

        except urllib.error.URLError as exc:
            is_last = attempt == max_retries - 1
            if is_last:
                logger.warning("openrouter: classification attempt %d/%d failed: %s",
                               attempt + 1, max_retries, exc)
            else:
                logger.debug("openrouter: classification attempt %d/%d failed: %s",
                             attempt + 1, max_retries, exc)
            if not is_last:
                time.sleep(0.5 * (attempt + 1))  # 0.5s, 1s backoff

        except Exception as exc:
            logger.debug("openrouter: classification error: %s", exc)
            return None

    return None


# ── Model validation ───────────────────────────────────────────────────

def _validate_model(model: str) -> bool:
    """Basic validation that a model string looks reasonable."""
    if not model or not isinstance(model, str):
        return False
    # Model strings should contain at least one slash (provider/model)
    parts = model.split("/")
    return len(parts) >= 2 and all(p.strip() for p in parts)


# ── Provider profile ───────────────────────────────────────────────────

class OpenRouterProfile(ProviderProfile):
    """OpenRouter aggregator — smart routing, provider preferences,
    reasoning config passthrough, Pareto Code, plus Requesty auto-cache.

    Zero core file changes: all config read from ~/.hermes/config.yaml,
    messages/base_url captured via prepare_messages/build_extra_body overrides.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._messages: list[dict[str, Any]] = []
        self._base_url: str = ""
        self._last_route_time: float = 0.0
        self._routing_count: int = 0

    def prepare_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Capture a shallow copy of messages for smart routing classification."""
        self._messages = list(messages) if messages else []
        return messages

    def build_extra_body(
        self, *, session_id: str | None = None, **context: Any
    ) -> dict[str, Any]:
        """Build extra_body with provider preferences, Pareto Code, requesty auto-cache."""
        body: dict[str, Any] = {}

        # Capture base_url for smart routing
        self._base_url = context.get("base_url", "") or self.base_url

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
                    existing = body.get("plugins")
                    if existing is None:
                        body["plugins"] = []
                        existing = body["plugins"]
                    existing.append(
                        {"id": "pareto-router", "min_coding_score": score_f}
                    )

        # Requesty auto-cache — read from config
        if _get_requesty_auto_cache():
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
        current_model = model or ""
        if (
            self._messages
            and self._base_url
            and current_model
            and current_model != "openrouter/auto"
        ):
            routing_cfg = _get_routing_config()
            if routing_cfg.get("enabled") and _is_new_user_task(self._messages):
                # Validate configured models
                router_model = routing_cfg.get("router_model", "")
                simple_model = routing_cfg.get("simple_model", "")
                complex_model = routing_cfg.get("complex_model", "")
                default_model = routing_cfg.get("default_model", "")

                if not _validate_model(router_model):
                    logger.warning(
                        "openrouter: invalid router_model %r — smart routing disabled for this turn",
                        router_model,
                    )
                else:
                    complexity = _classify_task(
                        self._messages, router_model, self._base_url
                    )

                    if complexity == "complex":
                        selected = complex_model or default_model
                    elif complexity == "simple":
                        selected = simple_model or default_model
                    else:
                        selected = ""

                    if selected and _validate_model(selected) and selected != current_model:
                        self._routing_count += 1
                        self._last_route_time = time.time()
                        logger.info(
                            "openrouter smart routing (#%d): %s → %s (%s)",
                            self._routing_count,
                            current_model,
                            selected,
                            complexity or "fallback",
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
