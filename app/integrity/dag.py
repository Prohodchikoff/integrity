from collections.abc import Mapping
from graphlib import CycleError, TopologicalSorter


def topological_order(graph: Mapping[str, set[str]]) -> tuple[str, ...]:
    """
    graph[model] = set of upstream models (dependencies) that must run first.
    """
    for node, preds in graph.items():
        for p in preds:
            if p not in graph:
                raise ValueError(f"Internal error: missing graph key for dependency {p!r}")

    ts = TopologicalSorter(graph)
    try:
        return tuple(ts.static_order())
    except CycleError as e:
        raise ValueError(f"Cyclic model dependencies: {e!s}") from e
