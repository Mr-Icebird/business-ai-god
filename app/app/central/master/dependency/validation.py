"""
BAIG MASTER — Dependency validation

Checks:
- no self-dependency
- no duplicate dependencies
- referenced tasks exist (when registry provided)
- no cycles in the dependency graph
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Mapping, Optional


class DependencyValidationError(ValueError):
    """Raised when dependency structure is invalid."""


def validate_basic(
    task_id: str,
    dependencies: tuple[str, ...],
    parent_task_id: Optional[str] = None,
) -> None:
    if task_id in dependencies:
        raise DependencyValidationError("Task cannot depend on itself")
    if parent_task_id is not None and parent_task_id == task_id:
        raise DependencyValidationError("Task cannot be its own parent")
    if len(dependencies) != len(set(dependencies)):
        raise DependencyValidationError("Duplicate dependencies are not allowed")


def validate_references(
    task_id: str,
    dependencies: tuple[str, ...],
    known_task_ids: Mapping[str, object],
    *,
    allow_forward_refs: bool = True,
) -> None:
    """
    Ensure dependency IDs refer to known tasks.
    allow_forward_refs=True permits dependencies not yet registered
    (useful during staged creation); set False for strict mode.
    """
    for dep_id in dependencies:
        if dep_id == task_id:
            raise DependencyValidationError("Task cannot depend on itself")
        if not allow_forward_refs and dep_id not in known_task_ids:
            raise DependencyValidationError(
                f"Unknown dependency reference: {dep_id}"
            )


def has_cycle(
    graph: Mapping[str, tuple[str, ...]],
) -> bool:
    """
    Kahn's algorithm.
    graph: task_id -> dependencies (edges: task depends on dep)
    Returns True if a cycle exists.
    """
    in_degree: dict[str, int] = defaultdict(int)
    dependents: dict[str, list[str]] = defaultdict(list)
    nodes = set(graph.keys())

    for task_id, deps in graph.items():
        for dep in deps:
            nodes.add(dep)
            dependents[dep].append(task_id)
            in_degree[task_id] += 1
        if task_id not in in_degree:
            in_degree[task_id] = in_degree.get(task_id, 0)

    for node in nodes:
        in_degree.setdefault(node, 0)

    queue = deque([n for n in nodes if in_degree[n] == 0])
    seen = 0

    while queue:
        node = queue.popleft()
        seen += 1
        for child in dependents.get(node, ()):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    return seen != len(nodes)


def validate_no_cycle(
    task_id: str,
    dependencies: tuple[str, ...],
    existing_graph: Mapping[str, tuple[str, ...]],
) -> None:
    """
    Validate that adding this task's dependencies would not create a cycle.
    existing_graph: current task_id -> dependencies
    """
    graph = dict(existing_graph)
    graph[task_id] = dependencies
    if has_cycle(graph):
        raise DependencyValidationError(
            f"Dependency cycle detected involving task {task_id}"
          )
