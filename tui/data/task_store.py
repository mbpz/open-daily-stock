"""Task store for tracking analysis jobs."""
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum
from datetime import datetime, timezone, timedelta

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"

@dataclass
class Task:
    id: str
    code: str
    status: TaskStatus
    timestamp: str
    result: Optional[str] = None
    error: Optional[str] = None

class TaskStore:
    def __init__(self):
        self._tasks: List[Task] = []

    def add_task(self, code: str) -> Task:
        tz_cn = timezone(timedelta(hours=8))
        task = Task(
            id=f"{code}-{datetime.now(tz_cn).strftime('%H%M%S')}",
            code=code,
            status=TaskStatus.PENDING,
            timestamp=datetime.now(tz_cn).strftime("%Y-%m-%d %H:%M"),
        )
        self._tasks.insert(0, task)
        return task

    def update_status(self, task_id: str, status: TaskStatus, result: str = None, error: str = None):
        for t in self._tasks:
            if t.id == task_id:
                t.status = status
                t.result = result
                t.error = error

    def get_tasks(self) -> List[Task]:
        return self._tasks