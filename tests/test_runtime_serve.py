import importlib

import pytest

from toolanything.core.registry import ToolRegistry


runtime_serve = importlib.import_module("toolanything.runtime.serve")


def test_runtime_serve_defaults_to_streamable_http(monkeypatch):
    registry = ToolRegistry()
    called = {}

    monkeypatch.setattr(
        runtime_serve,
        "run_streamable_http_server",
        lambda *, port, host, registry: called.setdefault(
            "streamable_http",
            {"port": port, "host": host, "registry": registry},
        ),
    )
    monkeypatch.setattr(
        runtime_serve,
        "run_legacy_http_server",
        lambda *, port, host, registry: called.setdefault(
            "legacy_http",
            {"port": port, "host": host, "registry": registry},
        ),
    )
    monkeypatch.setattr(
        runtime_serve,
        "run_stdio_server",
        lambda active_registry: called.setdefault("stdio", active_registry),
    )

    runtime_serve.serve(registry=registry, host="127.0.0.1", port=9090)

    assert called["streamable_http"]["port"] == 9090
    assert called["streamable_http"]["host"] == "127.0.0.1"
    assert called["streamable_http"]["registry"] is registry
    assert "legacy_http" not in called
    assert "stdio" not in called


def test_runtime_serve_supports_explicit_legacy_http(monkeypatch):
    registry = ToolRegistry()
    called = {}

    monkeypatch.setattr(
        runtime_serve,
        "run_streamable_http_server",
        lambda *, port, host, registry: called.setdefault("streamable_http", True),
    )
    monkeypatch.setattr(
        runtime_serve,
        "run_legacy_http_server",
        lambda *, port, host, registry: called.setdefault(
            "legacy_http",
            {"port": port, "host": host, "registry": registry},
        ),
    )

    runtime_serve.serve(registry=registry, host="127.0.0.1", port=9091, legacy_http=True)

    assert called["legacy_http"]["port"] == 9091
    assert called["legacy_http"]["host"] == "127.0.0.1"
    assert called["legacy_http"]["registry"] is registry
    assert "streamable_http" not in called


def test_runtime_serve_rejects_conflicting_transport_flags():
    registry = ToolRegistry()

    with pytest.raises(ValueError):
        runtime_serve.serve(registry=registry, stdio=True, legacy_http=True)
