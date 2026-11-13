"""
BAIG MASTER — Ordered multi-task locking

Prevents deadlocks by always acquiring task locks
in sorted task-id order.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Dict, Iterable, Iterator, List


class TaskLockManager:
    """
    Creates and acquires per-task RLocks in deterministic order.
    """

    def __init__(self) -> None:
        self._locks: Dict[str, threading.RLock] = {}
        self._guard = threading.Lock()

    def get_lock(self, task_id: str) -> threading.RLock:
        with self._guard:
            if task_id not in self._locks:
                self._locks[task_id] = threading.RLock()
            return self._locks[task_id]

    @contextmanager
    def acquire(self, task_ids: Iterable[str]) -> Iterator[None]:
        """
        Acquire locks for all given task IDs in sorted order.
        Releases in reverse order on exit.
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
