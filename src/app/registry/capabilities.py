"""Immutable key-to-handler capability registry."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class CapabilityRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, Callable[..., Any]] = {}

    def register(self, key: str, handler: Callable[..., Any]) -> None:
        if key in self._handlers:
            raise ValueError(f"capability already registered: {key}")
        self._handlers[key] = handler

    def get(self, key: str) -> Callable[..., Any]:
        if key not in self._handlers:
            raise KeyError(key)
        return self._handlers[key]

    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers))
