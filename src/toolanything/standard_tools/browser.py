"""Optional read-only browser-backed standard tools."""
from __future__ import annotations

from typing import Any

from toolanything.core import ToolRegistry, ToolSpec

from .options import StandardToolOptions
from .registration import positive_limit, register_callable
from .safety import DomainPolicy, StandardToolError, validate_url


def register_browser_readonly_tools(
    registry: ToolRegistry | None = None,
    options: StandardToolOptions | None = None,
) -> list[ToolSpec]:
    active_registry = registry or ToolRegistry.global_instance()
    active_options = options or StandardToolOptions()
    policy = DomainPolicy(
        allowed_domains=active_options.allowed_domains,
        blocked_domains=active_options.blocked_domains,
    )

    def browser_extract_text(url: str, max_chars: int = 20000) -> dict[str, Any]:
        """Extract text from a dynamic page through a caller-supplied read-only browser provider."""

        provider = active_options.browser_readonly_provider
        if provider is None:
            raise StandardToolError(
                "standard.browser.extract_text requires StandardToolOptions(browser_readonly_provider=...)"
            )
        validate_url(
            url,
            allow_private_network=active_options.allow_private_network,
            domain_policy=policy,
        )
        max_chars = positive_limit(max_chars, default=active_options.max_read_chars)
        result = provider(url, "extract_text", max_chars)
        return normalize_browser_result(url, result, max_chars)

    def browser_snapshot(url: str, max_chars: int = 20000) -> dict[str, Any]:
        """Capture a read-only page snapshot through a caller-supplied browser provider."""

        provider = active_options.browser_readonly_provider
        if provider is None:
            raise StandardToolError(
                "standard.browser.snapshot requires StandardToolOptions(browser_readonly_provider=...)"
            )
        validate_url(
            url,
            allow_private_network=active_options.allow_private_network,
            domain_policy=policy,
        )
        max_chars = positive_limit(max_chars, default=active_options.max_read_chars)
        result = provider(url, "snapshot", max_chars)
        return normalize_browser_result(url, result, max_chars)

    specs: list[ToolSpec] = []
    for func, name, description in (
        (
            browser_extract_text,
            "standard.browser.extract_text",
            "Extract text from a dynamic page through a caller-supplied read-only browser provider.",
        ),
        (
            browser_snapshot,
            "standard.browser.snapshot",
            "Capture a read-only page snapshot through a caller-supplied browser provider.",
        ),
    ):
        specs.append(
            register_callable(
                active_registry,
                func,
                name=name,
                description=description,
                category="browser",
                scopes=("browser:read", "net:http:get"),
                read_only=True,
                open_world=True,
                extra_metadata={"requires_provider": True},
            )
        )
    return specs


def normalize_browser_result(url: str, result: Any, max_chars: int) -> dict[str, Any]:
    if isinstance(result, str):
        text = result
        payload: dict[str, Any] = {"url": url, "text": text[:max_chars]}
        payload["truncated"] = len(text) > max_chars
        return payload
    if not isinstance(result, dict):
        raise StandardToolError("browser_readonly_provider must return str or dict")
    payload = dict(result)
    payload.setdefault("url", url)
    if isinstance(payload.get("text"), str):
        text = payload["text"]
        payload["text"] = text[:max_chars]
        payload["truncated"] = bool(payload.get("truncated", False)) or len(text) > max_chars
    return payload
