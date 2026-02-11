import asyncio
import logging
import threading
import time
from typing import List, Optional, Union, Callable, Any, Dict
from contextlib import asynccontextmanager
import aioredis
from aioredis.connection import EncodableT

from .config import settings

logger = logging.getLogger(__name__)


class RedisService:
    """Redis服务类"""

    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self._connecting = False
        self._last_health_check = 0
        self._health_check_interval = 60  # 健康检查间隔（秒）
        self._connection_retries = 0
        self._max_retries = 3

    async def _health_check(self):
        """定期健康检查，避免每次操作都检查"""
        current_time = time.time()
        if current_time - self._last_health_check < self._health_check_interval:
            return True

        if self.redis is None:
            return False

        try:
            await self.redis.ping()
            self._last_health_check = current_time
            self._connection_retries = 0  # 重置重试计数
            return True
        except Exception as e:
            logger.warning(f"Redis健康检查失败: {e}")
            return False

    async def _ensure_connection(self, force_check=False):
        """确保Redis连接可用，采用懒加载策略"""
        # 如果没有连接，直接初始化
        if self.redis is None:
            await self.init_redis()
            return

        # 如果强制检查或距离上次健康检查间隔较长，则进行检查
        if force_check or not await self._health_check():
            await self.init_redis()

    async def init_redis(self):
        """初始化Redis连接"""
        if self._connecting:
            # 如果正在连接，等待完成
            retry_count = 0
            while self._connecting and retry_count < 50:  # 最多等待5秒
                await asyncio.sleep(0.1)
                retry_count += 1
            return

        self._connecting = True
        try:
            # 如果存在旧连接，先关闭
            if self.redis:
                try:
                    await self.redis.close()
                except:
                    pass

            self.redis = await aioredis.from_url(
                settings.redis.url,
                decode_responses=True,
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                health_check_interval=30,
            )
            # 测试连接
            await self.redis.ping()
            self._last_health_check = time.time()
            self._connection_retries = 0
            logger.info("Redis连接成功")
        except Exception as e:
            self._connection_retries += 1
            logger.error(
                f"Redis连接失败 (尝试 {self._connection_retries}/{self._max_retries}): {e}"
            )
            self.redis = None
        finally:
            self._connecting = False

    async def close_redis(self):
        """关闭Redis连接"""
        if self.redis:
            try:
                await self.redis.close()
                logger.info("Redis连接已关闭")
            except Exception as e:
                logger.warning(f"关闭Redis连接时出错: {e}")
            finally:
                self.redis = None
                self._last_health_check = 0

    async def _execute_with_retry(self, operation, *args, **kwargs):
        """执行Redis操作，支持异常驱动的重连"""
        # 首次尝试：使用现有连接
        if self.redis is None:
            await self._ensure_connection()

        if self.redis is None:
            return None

        try:
            return await operation(*args, **kwargs)
        except (
            aioredis.ConnectionError,
            aioredis.TimeoutError,
            ConnectionResetError,
            BrokenPipeError,
            asyncio.exceptions.CancelledError,
        ) as e:
            # 网络相关错误，尝试重连
            logger.warning(f"Redis连接错误，尝试重连: {e}")

            if self._connection_retries < self._max_retries:
                await self._ensure_connection(force_check=True)
                if self.redis:
                    try:
                        return await operation(*args, **kwargs)
                    except Exception as retry_e:
                        logger.error(f"Redis重连后操作仍失败: {retry_e}")
            else:
                logger.error(f"Redis重连次数已达上限 ({self._max_retries})")
        except Exception as e:
            # 其他错误，记录但不重连
            logger.warning(f"Redis操作失败: {e}")

        return None

    async def get(self, key: str) -> Optional[str]:
        """获取缓存值"""
        return await self._execute_with_retry(self.redis.get, key)

    async def set(self, key: str, value: str, expire: Optional[int] = None, nx: bool = False, xx: bool = False) -> bool:
        """设置缓存值"""
        result = await self._execute_with_retry(self.redis.set, key, value, ex=expire, nx=nx, xx=xx)
        return result is not None and result

    async def delete(self, key: str) -> bool:
        """删除缓存值"""
        result = await self._execute_with_retry(self.redis.delete, key)
        return result is not None and result > 0

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        result = await self._execute_with_retry(self.redis.exists, key)
        return result is not None and result > 0

    async def expire(self, key: str, seconds: int) -> bool:
        """设置键的过期时间"""
        result = await self._execute_with_retry(self.redis.expire, key, seconds)
        return result is not None and result

    async def keys(self, pattern: str) -> List[str]:
        """获取匹配指定模式的键"""
        return await self._execute_with_retry(self.redis.keys, pattern)

    async def ttl(self, key: str) -> int:
        """获取键的剩余过期时间"""
        result = await self._execute_with_retry(self.redis.ttl, key)
        return result if result is not None else -2

    async def rpush(self, key: str, *values: str) -> int:
        """向列表右端推入元素"""
        result = await self._execute_with_retry(self.redis.rpush, key, *values)
        return result if result is not None else 0

    async def lpop(self, key: str) -> Optional[str]:
        """从列表左端弹出元素"""
        return await self._execute_with_retry(self.redis.lpop, key)

    async def llen(self, key: str) -> int:
        """获取列表长度"""
        result = await self._execute_with_retry(self.redis.llen, key)
        return result if result is not None else 0

    async def lindex(self, key: str, index: int) -> Optional[str]:
        """获取列表指定索引位置的元素"""
        return await self._execute_with_retry(self.redis.lindex, key, index)

    async def lset(self, key: str, index: int, value: str) -> bool:
        """设置列表指定索引位置的元素值"""
        result = await self._execute_with_retry(self.redis.lset, key, index, value)
        return result is not None and result

    async def lpush(self, key: str, *values: str) -> int:
        """向列表左端推入元素"""
        result = await self._execute_with_retry(self.redis.lpush, key, *values)
        return result if result is not None else 0

    async def rpop(self, key: str) -> Optional[str]:
        """从列表右端弹出元素"""
        return await self._execute_with_retry(self.redis.rpop, key)

    async def lrange(self, key: str, start: int = 0, end: int = -1) -> List[str]:
        """获取列表指定范围的元素"""
        result = await self._execute_with_retry(self.redis.lrange, key, start, end)
        return result if result is not None else []

    async def sadd(self, key: str, *values: str) -> int:
        """向集合添加元素"""
        result = await self._execute_with_retry(self.redis.sadd, key, *values)
        return result if result is not None else 0

    async def srem(self, key: str, *values: str) -> int:
        """从集合中移除元素"""
        result = await self._execute_with_retry(self.redis.srem, key, *values)
        return result if result is not None else 0

    async def smembers(self, key: str) -> set:
        """获取集合所有成员"""
        result = await self._execute_with_retry(self.redis.smembers, key)
        return result if result is not None else set()

    async def incr(self, key: str, amount: int = 1) -> int:
        """原子性增加键的值"""
        result = await self._execute_with_retry(self.redis.incr, key, amount)
        return result if result is not None else 0

    async def decr(self, key: str, amount: int = 1) -> int:
        """原子性减少键的值"""
        result = await self._execute_with_retry(self.redis.decr, key, amount)
        return result if result is not None else 0

    async def zcard(self, key: str) -> int:
        """获取有序集合的元素数量"""
        result = await self._execute_with_retry(self.redis.zcard, key)
        return result if result is not None else 0

    async def zadd(self, key: str, mapping: dict) -> int:
        """向有序集合添加元素"""
        result = await self._execute_with_retry(self.redis.zadd, key, mapping)
        return result if result is not None else 0

    async def zrange(self, key: str, start: int = 0, end: int = -1) -> List[str]:
        """获取有序集合指定范围的元素"""
        result = await self._execute_with_retry(self.redis.zrange, key, start, end)
        return result if result is not None else []

    async def zrem(self, key: str, *values: str) -> int:
        """从有序集合中删除元素"""
        result = await self._execute_with_retry(self.redis.zrem, key, *values)
        return result if result is not None else 0

    async def zincrby(self, key: str, increment: int, *values: str) -> str:
        """对有序集合中指定成员的分数加上增量 increment"""
        result = await self._execute_with_retry(self.redis.zincrby, key, increment, *values)
        return result if result is not None else '0'

    async def zscore(self, key: str, field: str):
        """获取有序集合中指定成员的分数"""
        result = await self._execute_with_retry(self.redis.zscore, key, field)
        return result if result is not None else '0'

    async def zrangebyscore(self, key: str, start: int = 0, end: int = -1) -> List[str]:
        """获取有序集合指定分数范围内的元素"""
        result = await self._execute_with_retry(self.redis.zrangebyscore, key, start, end)
        return result if result is not None else []

    async def zrank(self, key: str, field: str):
        """获取有序集合中指定成员的排名"""
        result = await self._execute_with_retry(self.redis.zrank, key, field)
        return result if result is not None else -1

    async def zrevrangebyscore(
        self,
        key: str,
        max: Union[str, float, int] = "+inf",
        min: Union[str, float, int] = "-inf",
        start: Optional[int] = None,
        num: Optional[int] = None,
        withscores: bool = False,
        score_cast_func: Callable[[Any], Union[float, int]] = float,
    ) -> List:
        """
        异步获取有序集合指定分数范围内的元素（倒序）
        参数与 redis-py 保持一致，内部转成 aioredis 关键字
        """
        # aioredis 使用 offset + count 而不是 start + num
        offset = start if start is not None else 0
        count = num if num is not None else -1   # -1 表示全部

        result = await self.redis.zrevrangebyscore(
            key,
            max=max,
            min=min,
            withscores=withscores,
            start=offset,
            num=count,
            score_cast_func=score_cast_func,
        )
        # aioredis 2.x 返回空列表时就是 []，无需再处理 None
        return result

    async def hget(self, key: str, field: str) -> str:
        """获取哈希表中的字段值"""
        result = await self._execute_with_retry(self.redis.hget, key, field)
        return result

    async def hset(self, key: str, field: str, *values: str) -> str:
        """设置哈希表中的字段值"""
        result = await self._execute_with_retry(self.redis.hset, key, field, *values)
        return result

    async def hmset(self, key: str, mapping: dict) -> str:
        """设置多个字段的值"""
        result = await self._execute_with_retry(self.redis.hset, key, None, None, mapping)
        return result

    async def hmget(self, key: str, *fields: str) -> List[str]:
        """获取多个字段的值"""
        result = await self._execute_with_retry(self.redis.hmget, key, *fields)
        return result if result is not None else []

    async def hgetall(self, key: str) -> Dict[str, str]:
        """获取哈希表所有字段的值"""
        result = await self._execute_with_retry(self.redis.hgetall, key)
        return result if result is not None else {}

    async def hincrby(self, key: str, field: str, amount: int = 1) -> int:
        """原子性增加哈希表字段的值"""
        result = await self._execute_with_retry(self.redis.hincrby, key, field, amount)
        return result

    def pipeline(self):
        """获取Redis管道对象"""
        return self.redis.pipeline()

    async def brpop(self, key: str, timeout: int = 0):
        """阻塞弹出元素"""
        return await self._execute_with_retry(self.redis.brpop, key, timeout)

    async def xadd(self, key: str, mapping: dict, id: str = '*', maxlen: int = None, approximate: bool = False):
        """添加元素到列表"""
        return await self._execute_with_retry(self.redis.xadd, key, mapping, id, maxlen, approximate)

    async def xread(self, streams: dict, block: int = 0, count: int = 0):
        """读取列表元素"""
        return await self._execute_with_retry(self.redis.xread, streams, count, block)

    async def xrange(self, key: str, start: str = '-', end: str = '+', count: int = None):
        """读取列表元素"""
        return await self._execute_with_retry(self.redis.xrange, key, start, end, count)

    async def eval(self, lua: str, numkeys: int, *keys_and_args:EncodableT):
        """执行Lua脚本"""
        return await self._execute_with_retry(self.redis.eval, lua, numkeys, *keys_and_args)

    async def ping(self):
        """测试Redis服务是否正常"""
        return await self._execute_with_retry(self.redis.ping)

    async def ltrim(self, key: str, start: int, end: int):
        """修剪列表"""
        return await self._execute_with_retry(self.redis.ltrim, key, start, end)




# 全局Redis服务实例
redis_service = RedisService()


async def get_redis() -> RedisService:
    """获取Redis服务实例"""
    return redis_service

def get_redis_sync() -> RedisService:
    return redis_service


_lock = threading.Lock()
_ref = 0

@asynccontextmanager
async def init_redis_client():
    global  _ref
    with _lock:
        if redis_service.redis is None:
            await redis_service.init_redis()
            _ref += 1
    yield
    with _lock:
        _ref -= 1
        if _ref == 0 and redis_service.redis is not None:
            await redis_service.close_redis()