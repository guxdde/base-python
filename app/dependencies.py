"""
TaskIQ 任务依赖注入模块

提供数据库会话、Redis 连接等依赖，供 TaskIQ 任务注入使用。
需要在 app/core/taskiq.py 中调用 taskiq_fastapi.init() 初始化。
"""

from typing import Annotated, AsyncGenerator

from fastapi import Request
from taskiq import TaskiqDepends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import dbm
from app.core.redis import redis_service, RedisService


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话依赖"""
    async with dbm.session() as session:
        yield session


async def get_redis_service() -> RedisService:
    """获取 Redis 服务依赖"""
    if redis_service.redis is None:
        await redis_service.init_redis()
    return redis_service


async def get_request(request: Request = TaskiqDepends()) -> Request:
    """获取 FastAPI Request 对象依赖"""
    return request


def inject_db_session():
    """数据库会话注入标记（用于 TaskiqDepends）"""
    return TaskiqDepends(get_db_session)


def inject_redis_service():
    """Redis 服务注入标记（用于 TaskiqDepends）"""
    return TaskiqDepends(get_redis_service)


DbSessionDep = Annotated[AsyncSession, TaskiqDepends(get_db_session)]
RedisDep = Annotated[RedisService, TaskiqDepends(get_redis_service)]
RequestDep = Annotated[Request, TaskiqDepends()]