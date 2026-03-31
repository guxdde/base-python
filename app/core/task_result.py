"""
任务结果存储

使用 Redis 存储任务执行状态和结果
"""
import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import redis

from app.core.config import settings


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class TaskResultStore:
    """任务结果存储管理器"""
    
    KEY_PREFIX = "dramatiq:result:"
    DEFAULT_TTL = 86400  # 24小时
    
    _redis_client: Optional[redis.Redis] = None
    
    @classmethod
    def get_redis(cls) -> redis.Redis:
        """获取 Redis 客户端"""
        if cls._redis_client is None:
            redis_conf = settings.redis
            cls._redis_client = redis.Redis(
                host=redis_conf.host,
                port=redis_conf.port,
                password=redis_conf.password if redis_conf.password else None,
                decode_responses=True,
            )
        return cls._redis_client
    
    @classmethod
    def generate_id(cls) -> str:
        """生成任务ID"""
        return str(uuid.uuid4())
    
    @classmethod
    def set_pending(cls, task_id: str, actor_name: str, args: tuple = (), kwargs: dict = None):
        """设置任务为待处理状态"""
        redis_client = cls.get_redis()
        data = {
            "task_id": task_id,
            "actor_name": actor_name,
            "args": list(args),
            "kwargs": kwargs or {},
            "status": TaskStatus.PENDING.value,
            "created_at": datetime.utcnow().isoformat(),
        }
        redis_client.setex(
            f"{cls.KEY_PREFIX}{task_id}",
            cls.DEFAULT_TTL,
            json.dumps(data)
        )
        return task_id
    
    @classmethod
    def set_started(cls, task_id: str):
        """设置任务为运行状态"""
        cls._update_status(task_id, TaskStatus.STARTED.value)
    
    @classmethod
    def set_success(cls, task_id: str, result: Any = None):
        """设置任务为成功状态"""
        cls._update_status(task_id, TaskStatus.SUCCESS.value, result=result)
    
    @classmethod
    def set_failure(cls, task_id: str, error: str):
        """设置任务为失败状态"""
        cls._update_status(task_id, TaskStatus.FAILURE.value, error=error)
    
    @classmethod
    def get_result(cls, task_id: str) -> Optional[dict]:
        """获取任务结果"""
        redis_client = cls.get_redis()
        data = redis_client.get(f"{cls.KEY_PREFIX}{task_id}")
        if data:
            return json.loads(data)
        return None
    
    @classmethod
    def delete_result(cls, task_id: str) -> bool:
        """删除任务结果"""
        redis_client = cls.get_redis()
        return bool(redis_client.delete(f"{cls.KEY_PREFIX}{task_id}"))
    
    @classmethod
    def _update_status(cls, task_id: str, status: str, **extra):
        """更新任务状态"""
        redis_client = cls.get_redis()
        key = f"{cls.KEY_PREFIX}{task_id}"
        data = redis_client.get(key)
        
        if data:
            data = json.loads(data)
            data.update({
                "status": status,
                "updated_at": datetime.utcnow().isoformat(),
                **extra
            })
            redis_client.setex(key, cls.DEFAULT_TTL, json.dumps(data))
