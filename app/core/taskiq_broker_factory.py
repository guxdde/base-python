"""
TaskIQ broker 工厂函数 - 支持多队列 worker 配置

提供不同的 broker 实例用于不同优先级的 worker。
Worker 通过 broker factory 函数来获取对应队列的 broker。
"""

from functools import lru_cache

from taskiq_aio_pika import AioPikaBroker, Queue

from .taskiq import redis_broker, task_queues, QUEUE_HIGH, QUEUE_DEFAULT, QUEUE_LOW


@lru_cache
def get_broker_for_default() -> AioPikaBroker:
    """获取监听 default 队列的 broker"""
    return redis_broker.with_queues(
        *[q for q in task_queues if q.name == QUEUE_DEFAULT]
    )


@lru_cache
def get_broker_for_high() -> AioPikaBroker:
    """获取监听 high_priority 队列的 broker"""
    return redis_broker.with_queues(
        *[q for q in task_queues if q.name == QUEUE_HIGH]
    )


@lru_cache
def get_broker_for_low() -> AioPikaBroker:
    """获取监听 low_priority 队列的 broker"""
    return redis_broker.with_queues(
        *[q for q in task_queues if q.name == QUEUE_LOW]
    )


@lru_cache
def get_broker_for_all() -> AioPikaBroker:
    """获取监听所有队列的 broker（默认行为）"""
    return redis_broker


def get_broker(queue_name: str) -> AioPikaBroker:
    """根据队列名称获取对应的 broker"""
    if queue_name == QUEUE_HIGH:
        return get_broker_for_high()
    elif queue_name == QUEUE_LOW:
        return get_broker_for_low()
    elif queue_name == QUEUE_DEFAULT:
        return get_broker_for_default()
    else:
        return get_broker_for_all()


__all__ = [
    "get_broker",
    "get_broker_for_default",
    "get_broker_for_high",
    "get_broker_for_low",
    "get_broker_for_all",
]