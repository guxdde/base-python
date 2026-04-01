"""
任务装饰器

为 Dramatiq actor 提供额外的配置选项
"""
import dramatiq
from typing import Callable

from app.core.dramatiq_broker import get_broker
from app.core.task_result import TaskResultStore


def dramatiq_task(
    queue: str = "default",
    time_limit: int = 120000,
    max_retries: int = 3,
):
    """
    Dramatiq 任务装饰器
    
    参数:
        queue: 任务队列名称
        time_limit: 时间限制 (毫秒)
        max_retries: 最大重试次数
    
    用法:
        @dramatiq_task(queue="default", time_limit=60000)
        async def my_task(data):
            return await process(data)
    """
    def decorator(fn: Callable):
        return dramatiq.actor(
            fn,
            queue_name=queue,
            time_limit=time_limit,
            max_retries=max_retries,
        )
    return decorator


def send_task(task_name: str, *args, queue: str = "default", **kwargs):
    """
    发送任务到队列
    
    参数:
        task_name: 任务名称 (actor 名称)
        *args: 位置参数
        queue: 队列名称
        **kwargs: 关键字参数
    
    返回:
        str: 任务ID
    """
    broker = get_broker()
    
    message_data = {
        "task_name": task_name,
        "args": args,
        "kwargs": kwargs,
    }
    
    return broker.enqueue(broker.encode_message(message_data), queue_name=queue)


def get_task_registry():
    """
    获取任务注册表
    
    返回:
        dict: actor 名称到 actor 的映射
    """
    return dramatiq.get_broker().actors.copy()
