"""
BAIG MASTER — Ordered multi-task locking.

Prevents deadlocks by acquiring all required task locks
in one deterministic global order (sorted task IDs).
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Dict, Iterable, Iterator, List


class TaskLockManager:
    """
    Manage per-task reentrant locks with ordered acquisition.

    Usage
    -----
    with lock_manager.acquire([task_id, *dependency_ids]):
        # safe critical section for readiness / transition
        ...
    """

    def __init__(self) -> None:
        """Create an empty lock registry protected by a process-local guard."""
        self._locks: Dict[str, threading.RLock] = {}
        self._guard = threading.Lock()

    def get_lock(self, task_id: str) -> threading.RLock:
        """
        Return the RLock for a task, creating it if needed.

        Parameters
        ----------
        task_id:
            Task identifier.

        Returns
        -------
        threading.RLock
            The lock associated with this task.
        """
        with self._guard:
            if task_id not in self._locks:
                self._locks[task_id] = threading.RLock()
            return self._locks[task_id]

    @contextmanager
    def acquire(self, task_ids: Iterable[str]) -> Iterator[None]:
        """
        Acquire locks for all provided task IDs in sorted order.

        Locks are released in reverse order on exit, including
        on exception.

        Parameters
        ----------
        task_ids:
            One or more task IDs that must be locked together.

        Yields
        ------
        None
            Control returns to the caller once all locks are held.
        """
        ordered: List[str] = sorted(set(task_ids))
        acquired: List[threading.RLock] = []
        try:
            for task_id in ordered:
                lock = self.get_lock(task_id)
                lock.acquire()
                acquired.append(lock)
            yield
        finally:
            for lock in reversed(acquired):
                lock.release()
