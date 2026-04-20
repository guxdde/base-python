"""
TaskIQ configuration and app setup for the FastAPI project.

This module replaces the previous Celery implementation with TaskIQ,
providing native async task processing and scheduling capabilities.
"""

import logging
from typing import Optional
from taskiq import TaskIQ
from taskiq.brokers.redis import RedisBroker
from taskiq.schedulers.scheduler import Scheduler
from taskiq.schedule_sources import CronScheduleSource
from taskiq.middleware import TaskiqMiddleware

from .config import settings

_logger = logging.getLogger(__name__)


# Create Redis broker
redis_broker = RedisBroker(
    broker_url=settings.redis.url,
    decode_responses=True,
)


# Create TaskIQ app
taskiq_app = TaskIQ(
    broker=redis_broker,
    name="fastapi_app",
)


# Configure task timeouts and retry policies
taskiq_app.task_defaults(
    max_retries=3,
    task_timeout=120,  # Default timeout
    soft_timeout=90,   # Soft timeout
)


# Custom middleware for logging and error handling
class LoggingMiddleware(TaskiqMiddleware):
    def pre_send(self, task_name: str, *args, **kwargs):
        _logger.info(f"Task {task_name} started with args={args}, kwargs={kwargs}")

    def post_send(self, task_name: str, result, *args, **kwargs):
        _logger.info(f"Task {task_name} completed with result={result}")

    def on_error(self, task_name: str, exception: Exception, *args, **kwargs):
        _logger.error(f"Task {task_name} failed with error={str(exception)}")


# Apply middleware
taskiq_app.middleware(LoggingMiddleware())


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
        # Apply TaskIQ task decorator
        task_func = taskiq_app.task(
            queue=queue,
            timeout=timeout,
            soft_timeout=soft_timeout,
            name=name or func.__name__,
            description=description,
        )(func)

        # Add custom attributes for compatibility
        task_func.queue = queue
        task_func.timeout = timeout
        task_func.soft_timeout = soft_timeout
        task_func.description = description
        task_func.tags = tags or []

        return task_func

    return decorator


# Create scheduler
taskiq_scheduler = Scheduler(
    broker=redis_broker,
    sources=[
        # Cron schedule sources will be added dynamically
    ],
)


# Helper functions for managing schedules
def add_cron_schedule(
    task_func,
    cron_expression: str,
    name: Optional[str] = None,
):
    """
    Add a cron schedule for a task.

    Args:
        task_func: The task function to schedule
        cron_expression: Cron expression (e.g., "*/10 * * * *")
        name: Optional schedule name
    """
    schedule_name = name or f"{task_func.__name__}_schedule"

    # Add to scheduler sources
    taskiq_scheduler.add_source(
        CronScheduleSource(
            schedule_name=schedule_name,
            task_name=task_func.taskiq_name,
            cron=cron_expression,
        )
    )

    _logger.info(f"Added cron schedule {schedule_name} for task {task_func.taskiq_name}")
    return schedule_name


def add_interval_schedule(
    task_func,
    seconds: int,
    name: Optional[str] = None,
):
    """
    Add an interval schedule for a task.

    Args:
        task_func: The task function to schedule
        seconds: Interval in seconds
        name: Optional schedule name
    """
    # Convert seconds to cron-like expression for now
    # TODO: Use TaskIQ's interval scheduling when available
    minutes = seconds // 60
    if minutes < 60:
        cron_expression = f"*/{minutes} * * * *"
    else:
        hours = minutes // 60
        cron_expression = f"0 */{hours} * * *"

    return add_cron_schedule(task_func, cron_expression, name)


# Export for easy import
__all__ = [
    "taskiq_app",
    "taskiq_task",
    "taskiq_scheduler",
    "add_cron_schedule",
    "add_interval_schedule",
    "redis_broker",
]