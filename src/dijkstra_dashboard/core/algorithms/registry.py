from __future__ import annotations

from typing import Dict, Iterable

from .base import AlgorithmSpec

_REGISTRY: Dict[str, AlgorithmSpec] = {}


def register_algorithm(spec: AlgorithmSpec) -> None:
    key = spec.name.lower()
    if key in _REGISTRY:
        raise ValueError(f"Algorithm already registered: {spec.name}")
    _REGISTRY[key] = spec


def get_algorithm_spec(name: str) -> AlgorithmSpec:
    key = name.lower()
    if key not in _REGISTRY:
        raise KeyError(f"Unknown algorithm: {name}")
    return _REGISTRY[key]


def list_algorithm_specs() -> Iterable[AlgorithmSpec]:
    return list(_REGISTRY.values())


def clear_registry() -> None:
    _REGISTRY.clear()
