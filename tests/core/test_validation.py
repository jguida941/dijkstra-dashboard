from dijkstra_dashboard.core.validation import validate_graph_data


def test_validation_negative_weight_warning():
    data = {
        "version": 1,
        "directed": False,
        "nodes": {
            "n1": {"label": "A", "x": 0, "y": 0},
            "n2": {"label": "B", "x": 0, "y": 0},
        },
        "edges": [
            {"id": "n1--n2", "start": "n1", "end": "n2", "weight": -1},
        ],
    }

    issues = validate_graph_data(data)
    codes = {issue.code for issue in issues}
    assert "negative_weight" in codes


def test_validation_missing_nodes_error():
    data = {
        "version": 1,
        "directed": False,
        "nodes": {
            "n1": {"label": "A", "x": 0, "y": 0},
        },
        "edges": [
            {"id": "n1--n2", "start": "n1", "end": "n2", "weight": 3},
        ],
    }

    issues = validate_graph_data(data)
    codes = {issue.code for issue in issues}
    assert "edge_missing_node" in codes


def test_validation_non_finite_weight_error():
    # NaN/inf slip past isinstance checks but silently break relaxation
    # (NaN comparisons are always False), so they must be load errors.
    for bad in (float("nan"), float("inf"), float("-inf")):
        data = {
            "version": 1,
            "directed": False,
            "nodes": {
                "n1": {"label": "A", "x": 0, "y": 0},
                "n2": {"label": "B", "x": 0, "y": 0},
            },
            "edges": [
                {"id": "n1--n2", "start": "n1", "end": "n2", "weight": bad},
            ],
        }

        issues = validate_graph_data(data)
        codes = {issue.code for issue in issues if issue.severity == "error"}
        assert "invalid_weight" in codes
