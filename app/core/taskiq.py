"""
TaskIQ configuration and app setup for the FastAPI project.

This module replaces the previous Celery implementation with TaskIQ,
providing native async task processing and scheduling capabilities.
Multi-queue priority support: high_priority > default > low_priority
"""

import os
import logging
from typing import Optional, List
from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_aio_pika import AioPikaBroker, Queue, QueueType
from taskiq_redis import RedisAsyncResultBackend

from .config import settings

_logger = logging.getLogger(__name__)

# Create Redis result backend
result_backend = RedisAsyncResultBackend(
    redis_url=settings.taskiq.result_backend_url,
    result_ex_time=3600,
)

# Priority queue configuration
QUEUE_HIGH = "high_priority"
QUEUE_DEFAULT = "default"
QUEUE_LOW = "low_priority"

# 获取环境变量中的队列名称（默认使用 default 队列）
QUEUE_NAME = os.getenv("TASKIQ_QUEUE", QUEUE_DEFAULT)

# 定义三个优先级的队列，使用不同的 routing_key 实现路由
task_queues: List[Queue] = [
    Queue(name=QUEUE_HIGH, routing_key=QUEUE_HIGH, max_priority=10),
    Queue(name=QUEUE_DEFAULT, routing_key=QUEUE_DEFAULT, max_priority=5),
    Queue(name=QUEUE_LOW, routing_key=QUEUE_LOW, max_priority=1),
]

# 使用 RabbitMQ 作为 broker
redis_broker = AioPikaBroker(
    url=settings.taskiq.broker_url,
    queue_name=QUEUE_NAME,  # 默认队列
    task_queues=task_queues,
)

_logger.info(
    f"TaskIQ broker initialized with queues: {[q.name for q in task_queues]}, "
    f"default queue: {QUEUE_NAME}"
)

# Alias for backward compatibility
taskiq_app = redis_broker


# Task decorator replacement for @celery_task
def taskiq_task(
    queue: str = QUEUE_DEFAULT,
    priority: Optional[int] = None,
    timeout: Optional[int] = None,
    soft_timeout: Optional[int] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[list] = None,
):
    """
    Decorator for creating TaskIQ tasks with multi-queue priority support.

    Args:
        queue: Task queue name - determines routing_key for message routing
               Options: "high_priority", "default", "low_priority"
        priority: Message priority (overrides queue default priority)
                  Higher number = higher priority in queue
        timeout: Hard timeout in seconds
        soft_timeout: Soft timeout in seconds
        name: Custom task name
        description: Task description
        tags: List of tags for the task

    Usage:
        @taskiq_task(queue="high_priority", priority=8)
        async def my_task(arg1: str):
            return {"result": arg1}
    """
    def decorator(func):
        labels = {"queue_name": queue}
        if priority is not None:
            labels["priority"] = priority

        task_func = redis_broker.task(
            timeout=timeout,
            soft_timeout=soft_timeout,
            name=name or func.__name__,
            labels=labels,
        )(func)

        task_func.queue = queue
        task_func.priority = priority
        task_func.timeout = timeout
        task_func.soft_timeout = soft_timeout
        task_func.description = description
        task_func.tags = tags or []

        _logger.debug(
            f"Registered task '{func.__name__}' with queue='{queue}', "
            f"priority={priority}, routing_key='{queue}'"
        )

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
    "result_backend",
    "QUEUE_NAME",
    "QUEUE_HIGH",
    "QUEUE_DEFAULT",
    "QUEUE_LOW",
    "task_queues",
]
