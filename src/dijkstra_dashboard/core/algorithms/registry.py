from __future__ import annotations

from typing import Dict, Iterable

from .base import AlgorithmSpec

_REGISTRY: Dict[str, AlgorithmSpec] = {}
_CLASSES: Dict[str, type] = {}


def register_algorithm(spec: AlgorithmSpec, algorithm_cls: type | None = None) -> None:
    key = spec.name.lower()
    if key in _REGISTRY:
        raise ValueError(f"Algorithm already registered: {spec.name}")
    _REGISTRY[key] = spec
    if algorithm_cls is not None:
        _CLASSES[key] = algorithm_cls


def get_algorithm_spec(name: str) -> AlgorithmSpec:
    key = name.lower()
    if key not in _REGISTRY:
        raise KeyError(f"Unknown algorithm: {name}")
    return _REGISTRY[key]


def list_algorithm_specs() -> Iterable[AlgorithmSpec]:
    return list(_REGISTRY.values())


def get_algorithm_class(name: str) -> type:
    key = name.lower()
    if key not in _REGISTRY or key not in _CLASSES:
        raise KeyError(f"Unknown algorithm: {name}")
    return _CLASSES[key]


def create_algorithm(name: str):
    return get_algorithm_class(name)()


def clear_registry() -> None:
    _REGISTRY.clear()
    _CLASSES.clear()
