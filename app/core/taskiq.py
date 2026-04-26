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
from taskiq_aio_pika import AioPikaBroker, Queue, QueueType, Exchange
from taskiq_redis import RedisAsyncResultBackend
from aio_pika import ExchangeType
import taskiq_fastapi

from .config import settings

_logger = logging.getLogger(__name__)

# Exchange 配置 - 使用 DIRECT 类型进行精确路由
taskiq_exchange = Exchange(
    name="taskiq_direct",
    type=ExchangeType.DIRECT,
    durable=True,
    declare=True,
)

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

# 定义三个优先级的队列，使用相同的 max_priority 以支持细粒度优先级控制
# 队列通过 routing_key 实现路由，消息通过 priority label 设置优先级
task_queues: List[Queue] = [
    Queue(name=QUEUE_HIGH, routing_key=QUEUE_HIGH, max_priority=10),
    Queue(name=QUEUE_DEFAULT, routing_key=QUEUE_DEFAULT, max_priority=10),
    Queue(name=QUEUE_LOW, routing_key=QUEUE_LOW, max_priority=10),
]

# 使用 RabbitMQ 作为 broker
broker = AioPikaBroker(
    url=settings.taskiq.broker_url,
    # queue_name=QUEUE_NAME,
    task_queues=task_queues,
    exchange=taskiq_exchange,
)

_logger.info(
    f"TaskIQ broker initialized with queues: {[q.name for q in task_queues]}, "
    f"default queue: {QUEUE_NAME}"
)

# Alias for backward compatibility
taskiq_app = broker


# TaskIQ Scheduler for periodic tasks
scheduler = TaskiqScheduler(
    broker=broker,
    sources=[LabelScheduleSource(broker)],
)

taskiq_fastapi.init(broker, "app.factory:create_app")


# Export for easy import
__all__ = [
    "taskiq_app",
    "broker",
    "scheduler",
    "result_backend",
    "taskiq_exchange",
    "QUEUE_NAME",
    "QUEUE_HIGH",
    "QUEUE_DEFAULT",
    "QUEUE_LOW",
    "task_queues",
]
