import importlib

import pytest

from dijkstra_dashboard.core.algorithms import registry
from dijkstra_dashboard.core.algorithms.dijkstra import DijkstraAlgorithm


def _snapshot_registry():
    return dict(registry._REGISTRY), dict(getattr(registry, "_CLASSES", {}))


def _restore_registry(specs, classes):
    registry.clear_registry()
    for key, spec in specs.items():
        cls = classes.get(key)
        try:
            registry.register_algorithm(spec, cls)
        except TypeError:
            registry.register_algorithm(spec)


def test_package_import_registers_dijkstra_and_can_create_algorithm():
    specs, classes = _snapshot_registry()
    try:
        registry.clear_registry()
        import dijkstra_dashboard.core.algorithms as algorithms

        importlib.reload(algorithms.dijkstra)

        assert registry.get_algorithm_spec("dijkstra").name == "dijkstra"
        assert registry.get_algorithm_class("dijkstra") is algorithms.dijkstra.DijkstraAlgorithm
        assert isinstance(registry.create_algorithm("dijkstra"), algorithms.dijkstra.DijkstraAlgorithm)
    finally:
        _restore_registry(specs, classes)


def test_get_algorithm_class_unknown_raises_key_error():
    with pytest.raises(KeyError, match="Unknown algorithm: unknown"):
        registry.get_algorithm_class("unknown")


def test_dijkstra_step_line_map_indices_and_observed_steps(sample_graph):
    steps = list(DijkstraAlgorithm().iter_steps(sample_graph, {"start": "A", "target": "F"}))

    assert DijkstraAlgorithm.pseudocode
    for indices in DijkstraAlgorithm.step_line_map.values():
        assert all(0 <= index < len(DijkstraAlgorithm.pseudocode) for index in indices)

    for step in steps:
        assert DijkstraAlgorithm.lines_for_step(step)
