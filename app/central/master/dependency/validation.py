"""
BAIG MASTER — Dependency validation subsystem.

Responsibilities:
- Reject self-dependencies and duplicate edges.
- Optionally require that referenced tasks exist.
- Detect cycles using Kahn's algorithm before a task is accepted.

This module does not lock tasks and does not change task state.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Mapping, Optional


class DependencyValidationError(ValueError):
    """Raised when a dependency structure is invalid for BAIG."""


def validate_basic(
    task_id: str,
    dependencies: tuple[str, ...],
    parent_task_id: Optional[str] = None,
) -> None:
    """
    Validate local dependency rules for one task.

    Checks:
    - task does not depend on itself
    - task is not its own parent
    - dependency list has no duplicates

    Parameters
    ----------
    task_id:
        ID of the task being validated.
    dependencies:
        Task IDs this task depends on.
    parent_task_id:
        Optional parent task ID.

    Raises
    ------
    DependencyValidationError
        If any local rule is violated.
    """
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
    Ensure dependency references are acceptable.

    Parameters
    ----------
    task_id:
        ID of the task being validated.
    dependencies:
        Declared dependency IDs.
    known_task_ids:
        Mapping of currently known task IDs.
    allow_forward_refs:
        If True, unknown dependency IDs are allowed
        (useful during staged creation).
        If False, every dependency must already exist.

    Raises
    ------
    DependencyValidationError
        If a reference is illegal under the chosen policy.
    """
    for dep_id in dependencies:
        if dep_id == task_id:
            raise DependencyValidationError("Task cannot depend on itself")
        if not allow_forward_refs and dep_id not in known_task_ids:
            raise DependencyValidationError(
                f"Unknown dependency reference: {dep_id}"
            )


def has_cycle(graph: Mapping[str, tuple[str, ...]]) -> bool:
    """
    Detect whether a directed dependency graph contains a cycle.

    Uses Kahn's algorithm (BFS by in-degree).

    Complexity
    ----------
    Time:  O(V + E)
    Space: O(V)

    Parameters
    ----------
    graph:
        Mapping of task_id -> dependency IDs.
        Edge meaning: task depends on dependency.

    Returns
    -------
    bool
        True if a cycle exists, otherwise False.
    """
    in_degree: dict[str, int] = defaultdict(int)
    dependents: dict[str, list[str]] = defaultdict(list)
    nodes = set(graph.keys())

    for task_id, deps in graph.items():
        for dep in deps:
            nodes.add(dep)
            dependents[dep].append(task_id)
            in_degree[task_id] += 1

    for node in nodes:
        in_degree.setdefault(node, 0)

    queue = deque(n for n in nodes if in_degree[n] == 0)
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
    Reject a new task if adding it would create a dependency cycle.

    Parameters
    ----------
    task_id:
        ID of the candidate task.
    dependencies:
        Dependencies declared for the candidate task.
    existing_graph:
        Current task_id -> dependencies map already known to MASTER.

    Raises
    ------
    DependencyValidationError
        If the resulting graph would contain a cycle.
    """
    graph = dict(existing_graph)
    graph[task_id] = dependencies
    if has_cycle(graph):
        raise DependencyValidationError(
            f"Dependency cycle detected involving task {task_id}"
                )
