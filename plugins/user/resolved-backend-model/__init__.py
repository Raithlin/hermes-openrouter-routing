"""Resolved backend model plugin — captures OpenRouter auto-routing results.

When OpenRouter auto-routing returns a different model than requested,
this plugin stores the resolved backend model in a module-level dict
keyed by session_id. The status bar can read this to display which
model was actually used for the response.

Usage from status bar or other components::

    from resolved_backend_model import resolved_models
    actual_model = resolved_models.get(session_id)
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Session-scoped storage ───────────────────────────────────────────
# Maps session_id -> resolved_backend_model string
resolved_models: dict[str, str] = {}


def _on_post_api_request(
    task_id: str,
    session_id: str,
    platform: str,
    model: str,
    provider: str,
    response: Any,
    assistant_message: str,
    api_kwargs: dict[str, Any],
    api_call_count: int,
) -> None:
    """Post-api-request hook: capture resolved backend model from OpenRouter.

    Checks the response for a `provider` field (from OpenRouter auto-routing)
    that differs from the requested model. If found, stores the resolved
    backend model in the session-scoped dict.
    """
    if not response:
        return

    # OpenRouter auto-routing returns the resolved model in the response
    # under various paths. Try the most common ones.
    resolved_model = None

    # Check response.model (OpenRouter sets this to the actual model used)
    if hasattr(response, "model") and response.model:
        resolved_model = response.model

    # Check response.get('model') for dict-like responses
    if not resolved_model and isinstance(response, dict):
        resolved_model = response.get("model")

    # Check response.provider for OpenRouter provider info
    if not resolved_model:
        provider_info = None
        if hasattr(response, "provider"):
            provider_info = response.provider
        elif isinstance(response, dict):
            provider_info = response.get("provider")

        if provider_info:
            if isinstance(provider_info, dict):
                resolved_model = provider_info.get("model")

    # Only store if the resolved model differs from the requested model
    if resolved_model and resolved_model != model:
        resolved_models[session_id] = resolved_model
        logger.debug(
            "resolved-backend-model: session=%s requested=%s resolved=%s",
            session_id,
            model,
            resolved_model,
        )


def register(ctx) -> None:
    """Register the post_api_request hook for resolved backend model tracking."""
    ctx.register_hook("post_api_request", _on_post_api_request)