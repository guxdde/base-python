import logging
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field

_logger = logging.getLogger(__name__)


@dataclass
class TaskInfo:
    name: str
    func: Callable
    queue: Optional[str] = None
    soft_time_limit: Optional[int] = None
    time_limit: Optional[int] = None
    options: Dict[str, Any] = field(default_factory=dict)
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)


class TaskRegistry:
    _tasks: Dict[str, TaskInfo] = {}

    @classmethod
    def register(
        cls,
        name: str,
        func: Callable,
        queue: Optional[str] = None,
        soft_time_limit: Optional[int] = None,
        time_limit: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> TaskInfo:
        task_info = TaskInfo(
            name=name,
            func=func,
            queue=queue,
            soft_time_limit=soft_time_limit,
            time_limit=time_limit,
            options=options or {},
            description=description,
            tags=tags or [],
        )
        cls._tasks[name] = task_info
        _logger.info(f"Task registered: {name} (queue: {queue})")
        return task_info

    @classmethod
    def get(cls, name: str) -> Optional[TaskInfo]:
        return cls._tasks.get(name)

    @classmethod
    def all(cls) -> List[TaskInfo]:
        return list(cls._tasks.values())

    @classmethod
    def get_by_queue(cls, queue: str) -> List[TaskInfo]:
        return [t for t in cls._tasks.values() if t.queue == queue]

    @classmethod
    def unregister(cls, name: str) -> bool:
        if name in cls._tasks:
            del cls._tasks[name]
            _logger.info(f"Task unregistered: {name}")
            return True
        return False

    @classmethod
    def clear(cls) -> None:
        cls._tasks.clear()
        _logger.info("All tasks cleared from registry")

    @classmethod
    def get_names(cls) -> List[str]:
        return list(cls._tasks.keys())


task_registry = TaskRegistry()
