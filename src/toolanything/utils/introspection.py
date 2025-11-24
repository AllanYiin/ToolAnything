from __future__ import annotations

from typing import Callable


def get_docstring(fn: Callable) -> str | None:
    return (fn.__doc__ or "").strip() or None
