"""
TaskIQ configuration and app setup for the FastAPI project.

This module replaces the previous Celery implementation with TaskIQ,
providing native async task processing and scheduling capabilities.
"""

import logging
from typing import Optional
from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import RedisStreamBroker, RedisAsyncResultBackend

from .config import settings

_logger = logging.getLogger(__name__)

# Create Redis broker
result_backend = RedisAsyncResultBackend(
    redis_url=settings.redis.url,
    result_ex_time=3600,
)

redis_broker = RedisStreamBroker(
    url=settings.redis.url,
).with_result_backend(result_backend)

# Alias for backward compatibility
taskiq_app = redis_broker


# Task decorator replacement for @celery_task
def taskiq_task(
    queue: str = "default",
    timeout: Optional[int] = None,
    soft_timeout: Optional[int] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[list] = None,
):
    """
    Decorator for creating TaskIQ tasks.

    This replaces the custom @celery_task decorator with TaskIQ's native
    task decorator, maintaining similar functionality.

    Args:
        queue: Task queue name
        timeout: Hard timeout in seconds
        soft_timeout: Soft timeout in seconds
        name: Custom task name
        description: Task description
        tags: List of tags for the task

    Usage:
        @taskiq_task(queue="high", timeout=60)
        async def my_task(arg1: str, arg2: int):
            return {"result": f"{arg1}_{arg2}"}
    """
    def decorator(func):
        task_func = redis_broker.task(
            queue=queue,
            timeout=timeout,
            soft_timeout=soft_timeout,
            name=name or func.__name__,
        )(func)

        task_func.queue = queue
        task_func.timeout = timeout
        task_func.soft_timeout = soft_timeout
        task_func.description = description
        task_func.tags = tags or []

        return task_func

    return decorator


# TaskIQ Scheduler for periodic tasks
scheduler = TaskiqScheduler(
    broker=redis_broker,
    sources=[LabelScheduleSource(redis_broker)],
)


# Export for easy import
__all__ = [
    "taskiq_app",
    "redis_broker",
    "taskiq_task",
    "scheduler",
]
