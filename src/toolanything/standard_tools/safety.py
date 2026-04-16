"""Safety helpers for ToolAnything standard tools."""
from __future__ import annotations

import ipaddress
import re
import socket
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlparse

from .options import StandardToolRoot


class StandardToolError(ValueError):
    """Raised when a standard tool rejects unsafe input or policy violations."""


BINARY_EXTENSIONS = {
    ".7z",
    ".avi",
    ".bin",
    ".bmp",
    ".class",
    ".dll",
    ".doc",
    ".docx",
    ".exe",
    ".gif",
    ".gz",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".mov",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".pyc",
    ".rar",
    ".so",
    ".tar",
    ".wasm",
    ".webp",
    ".xls",
    ".xlsx",
    ".zip",
}
METADATA_HOSTS = {
    "metadata.amazonaws.com",
    "metadata.google.internal",
    "metadata.goog",
}
CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")


def has_binary_extension(path: str | Path) -> bool:
    return Path(path).suffix.lower() in BINARY_EXTENSIONS


def resolve_under_root(
    roots: Mapping[str, StandardToolRoot],
    root_id: str,
    relative_path: str = ".",
    *,
    require_writable: bool = False,
) -> Path:
    selected_root_id = root_id.strip() if root_id else next(iter(roots))
    if selected_root_id not in roots:
        raise StandardToolError(f"unknown root_id: {selected_root_id}")

    root = roots[selected_root_id]
    if require_writable and not root.writable:
        raise StandardToolError(f"root_id is not writable: {selected_root_id}")

    if not relative_path:
        relative_path = "."
    requested = Path(relative_path)
    if requested.is_absolute():
        raise StandardToolError("relative_path must not be absolute")

    root_path = Path(root.path).expanduser().resolve()
    target = root_path / requested
    target_for_check = target.resolve() if target.exists() else target.parent.resolve()

    try:
        target_for_check.relative_to(root_path)
    except ValueError as exc:
        raise StandardToolError("path escapes configured root") from exc

    return target


def ensure_text_file(path: Path, *, max_file_bytes: int) -> None:
    if has_binary_extension(path):
        raise StandardToolError("binary file extensions are not readable as text")
    if path.exists() and path.is_file() and path.stat().st_size > max_file_bytes:
        raise StandardToolError("file exceeds configured max_file_bytes")


def is_domain_match(hostname: str, pattern: str) -> bool:
    host = hostname.lower().strip(".")
    rule = pattern.lower().strip(".")
    if not rule:
        return False
    if rule.startswith("*."):
        suffix = rule[2:]
        return host.endswith(f".{suffix}") and host != suffix
    return host == rule or host.endswith(f".{rule}")


class DomainPolicy:
    def __init__(
        self,
        *,
        allowed_domains: tuple[str, ...] = (),
        blocked_domains: tuple[str, ...] = (),
    ) -> None:
        self.allowed_domains = tuple(domain.strip() for domain in allowed_domains if domain.strip())
        self.blocked_domains = tuple(domain.strip() for domain in blocked_domains if domain.strip())

    def check(self, url: str) -> None:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        if any(is_domain_match(hostname, pattern) for pattern in self.blocked_domains):
            raise StandardToolError(f"blocked domain: {hostname}")
        if self.allowed_domains and not any(
            is_domain_match(hostname, pattern) for pattern in self.allowed_domains
        ):
            raise StandardToolError(f"domain is not in allowed_domains: {hostname}")


def validate_url(url: str, *, allow_private_network: bool, domain_policy: DomainPolicy) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise StandardToolError("only http and https URLs are allowed")
    if not parsed.hostname:
        raise StandardToolError("URL hostname is required")

    hostname = parsed.hostname.lower().strip(".")
    if hostname in METADATA_HOSTS:
        raise StandardToolError("cloud metadata hosts are not allowed")
    if _looks_like_metadata_ip(hostname):
        raise StandardToolError("cloud metadata IPs are not allowed")

    domain_policy.check(url)
    for address in _resolve_addresses(hostname):
        _validate_ip_address(address, allow_private_network=allow_private_network)


def validate_ip_text(address: str, *, allow_private_network: bool) -> None:
    """Validate a concrete peer IP address using the standard network policy."""

    _validate_ip_address(ipaddress.ip_address(address), allow_private_network=allow_private_network)


def _resolve_addresses(hostname: str) -> list[ipaddress._BaseAddress]:
    try:
        raw_addresses = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise StandardToolError(f"could not resolve hostname: {hostname}") from exc

    addresses: list[ipaddress._BaseAddress] = []
    for item in raw_addresses:
        sockaddr = item[4]
        if not sockaddr:
            continue
        addresses.append(ipaddress.ip_address(sockaddr[0]))
    if not addresses:
        raise StandardToolError(f"could not resolve hostname: {hostname}")
    return addresses


def _validate_ip_address(address: ipaddress._BaseAddress, *, allow_private_network: bool) -> None:
    if address.is_unspecified or address.is_multicast or address.is_reserved:
        raise StandardToolError(f"unsafe resolved IP address: {address}")
    if address in CGNAT_NETWORK:
        raise StandardToolError(f"carrier-grade NAT address is not allowed: {address}")
    if allow_private_network:
        return
    if address.is_private or address.is_loopback or address.is_link_local:
        raise StandardToolError(f"private network address is not allowed: {address}")


def _looks_like_metadata_ip(hostname: str) -> bool:
    normalized = hostname.strip("[]")
    if normalized == "169.254.169.254":
        return True
    if re.fullmatch(r"0*169\.0*254\.0*169\.0*254", normalized):
        return True
    return False
