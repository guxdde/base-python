"""
定时任务模块

此模块用于定义 Dramatiq 定时任务。
定时任务通过 @dramatiq.actor 装饰器注册，会在应用启动时自动加载。

定义方式：
1. 使用 @dramatiq.actor(periodic=cron(...)) - Cron 表达式定时任务
2. 使用 @dramatiq.actor() - 手动触发任务
"""

# 初始化数据库和 Redis 连接（Worker/Periodiq 启动时需要）
import asyncio
from app.core.database import init_databases
from app.core.redis import redis_service

asyncio.get_event_loop().run_until_complete(init_databases())
asyncio.get_event_loop().run_until_complete(redis_service.init_redis())
from app.core.dramatiq_broker import rabbitmq_broker

# 导入并注册定时任务
from app.tasks import scheduled_tasks  # noqa: F401

__all__ = [
    'rabbitmq_broker',
    'scheduled_tasks'
]