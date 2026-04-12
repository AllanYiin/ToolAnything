"""Read-only web standard tools."""
from __future__ import annotations

import html
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from html.parser import HTMLParser
from typing import Any

from toolanything.core import ToolRegistry, ToolSpec

from .options import StandardToolOptions
from .registration import positive_limit, register_callable
from .safety import DomainPolicy, StandardToolError, validate_url


def register_web_readonly_tools(
    registry: ToolRegistry | None = None,
    options: StandardToolOptions | None = None,
) -> list[ToolSpec]:
    active_registry = registry or ToolRegistry.global_instance()
    active_options = options or StandardToolOptions()
    policy = DomainPolicy(
        allowed_domains=active_options.allowed_domains,
        blocked_domains=active_options.blocked_domains,
    )
    specs: list[ToolSpec] = []

    def web_fetch(url: str, max_bytes: int = 0) -> dict[str, Any]:
        """Fetch a web page or text resource with SSRF protections and size limits."""

        limit = positive_limit(max_bytes, default=active_options.max_web_bytes)
        return fetch_url(url, options=active_options, policy=policy, max_bytes=limit)

    def web_extract_text(url: str, max_chars: int = 20000) -> dict[str, Any]:
        """Fetch a URL and return readable text extracted from HTML or plain text."""

        response = fetch_url(
            url,
            options=active_options,
            policy=policy,
            max_bytes=active_options.max_web_bytes,
        )
        text = response["text"]
        title = ""
        if "html" in response["content_type"].lower():
            parser = HTMLTextExtractor()
            parser.feed(text)
            text = parser.text()
            title = parser.title
        max_chars = positive_limit(max_chars, default=active_options.max_read_chars)
        return {
            "url": response["url"],
            "final_url": response["final_url"],
            "title": title,
            "text": text[:max_chars],
            "truncated": len(text) > max_chars or response["truncated"],
        }

    def web_extract_links(url: str, limit: int = 100) -> dict[str, Any]:
        """Fetch a URL and return normalized links from HTML anchors."""

        response = fetch_url(
            url,
            options=active_options,
            policy=policy,
            max_bytes=active_options.max_web_bytes,
        )
        parser = HTMLLinkExtractor(response["final_url"])
        parser.feed(response["text"])
        max_items = positive_limit(limit, default=100)
        return {
            "url": response["url"],
            "final_url": response["final_url"],
            "links": parser.links[:max_items],
            "truncated": len(parser.links) > max_items or response["truncated"],
        }

    def web_search(query: str, limit: int = 10) -> dict[str, Any]:
        """Run a configured search provider and normalize its result shape."""

        if active_options.search_provider is None:
            raise StandardToolError(
                "standard.web.search requires StandardToolOptions(search_provider=...)"
            )
        max_items = min(positive_limit(limit, default=10), active_options.max_search_results)
        raw_results = active_options.search_provider(query, max_items)
        return {
            "query": query,
            "results": normalize_search_results(raw_results, max_items),
        }

    specs.append(
        register_callable(
            active_registry,
            web_fetch,
            name="standard.web.fetch",
            description="Fetch an HTTP(S) resource with SSRF protections, domain policy, redirect validation, and byte limits.",
            category="web",
            scopes=("net:http:get",),
            read_only=True,
            open_world=True,
        )
    )
    specs.append(
        register_callable(
            active_registry,
            web_extract_text,
            name="standard.web.extract_text",
            description="Fetch a URL and extract readable text from HTML or plain text with the standard web safety policy.",
            category="web",
            scopes=("net:http:get",),
            read_only=True,
            open_world=True,
        )
    )
    specs.append(
        register_callable(
            active_registry,
            web_extract_links,
            name="standard.web.extract_links",
            description="Fetch a URL and extract normalized links from HTML anchors with the standard web safety policy.",
            category="web",
            scopes=("net:http:get",),
            read_only=True,
            open_world=True,
        )
    )
    specs.append(
        register_callable(
            active_registry,
            web_search,
            name="standard.web.search",
            description="Search the web through a caller-supplied provider and return normalized title/url/snippet results.",
            category="web",
            scopes=("net:search",),
            read_only=True,
            open_world=True,
            extra_metadata={"requires_provider": True},
        )
    )
    return specs


def fetch_url(
    url: str,
    *,
    options: StandardToolOptions,
    policy: DomainPolicy,
    max_bytes: int,
) -> dict[str, Any]:
    current_url = url
    for _ in range(6):
        validate_url(
            current_url,
            allow_private_network=options.allow_private_network,
            domain_policy=policy,
        )
        request = urllib.request.Request(
            current_url,
            headers={"User-Agent": options.web_user_agent, "Accept": "text/*, application/json, application/xml"},
            method="GET",
        )
        try:
            opener = urllib.request.build_opener(NoRedirectHandler)
            with opener.open(request, timeout=options.web_timeout_sec) as response:
                raw = response.read(max_bytes + 1)
                content_type = response.headers.get("Content-Type", "")
                charset = response.headers.get_content_charset() or "utf-8"
                text = raw[:max_bytes].decode(charset, errors="replace")
                return {
                    "url": url,
                    "final_url": response.geturl(),
                    "status": response.status,
                    "content_type": content_type,
                    "encoding": charset,
                    "text": text,
                    "bytes_read": min(len(raw), max_bytes),
                    "truncated": len(raw) > max_bytes,
                }
        except urllib.error.HTTPError as exc:
            if exc.code in {301, 302, 303, 307, 308}:
                location = exc.headers.get("Location")
                if not location:
                    raise StandardToolError("redirect response is missing Location") from exc
                current_url = urllib.parse.urljoin(current_url, location)
                continue
            raw = exc.read(max_bytes + 1)
            text = raw[:max_bytes].decode("utf-8", errors="replace")
            return {
                "url": url,
                "final_url": exc.geturl(),
                "status": exc.code,
                "content_type": exc.headers.get("Content-Type", ""),
                "encoding": "utf-8",
                "text": text,
                "bytes_read": min(len(raw), max_bytes),
                "truncated": len(raw) > max_bytes,
            }
        except urllib.error.URLError as exc:
            raise StandardToolError(f"request failed: {exc.reason}") from exc

    raise StandardToolError("too many redirects")


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


class HTMLTextExtractor(HTMLParser):
    SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "header", "footer"}
    BLOCK_TAGS = {"article", "aside", "br", "div", "h1", "h2", "h3", "li", "main", "p", "section", "td", "th", "tr"}

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._in_title = False
        self._title_parts: list[str] = []
        self._skip_depth = 0

    @property
    def title(self) -> str:
        return html.unescape(" ".join(part.strip() for part in self._title_parts if part.strip()))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        lowered = tag.lower()
        if lowered in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if lowered == "title":
            self._in_title = True
        if lowered in self.BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in self.SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if lowered == "title":
            self._in_title = False
        if lowered in self.BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self._title_parts.append(text)
        else:
            self._parts.append(text)

    def text(self) -> str:
        raw = html.unescape(" ".join(self._parts))
        lines = [reduced for line in raw.splitlines() if (reduced := " ".join(line.split()))]
        return "\n".join(lines)


class HTMLLinkExtractor(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attributes = dict(attrs)
        href = attributes.get("href")
        if not href:
            return
        normalized = urllib.parse.urljoin(self.base_url, href)
        self.links.append({"url": normalized, "label": attributes.get("title") or ""})


def normalize_search_results(raw_results: Any, limit: int) -> list[dict[str, Any]]:
    if isinstance(raw_results, dict) and isinstance(raw_results.get("results"), list):
        raw_items = raw_results["results"]
    elif isinstance(raw_results, list):
        raw_items = raw_results
    else:
        raise StandardToolError("search_provider must return a list or {'results': list}")

    normalized: list[dict[str, Any]] = []
    for item in raw_items[:limit]:
        if isinstance(item, str):
            normalized.append({"title": item, "url": "", "snippet": ""})
            continue
        if not isinstance(item, Mapping):
            continue
        normalized.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url") or item.get("link", ""),
                "snippet": item.get("snippet") or item.get("summary", ""),
            }
        )
    return normalized
