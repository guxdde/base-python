import hashlib
import json
import functools
from typing import Callable, Optional, List
from app.core.redis import get_redis_sync


class BaseServiceCache:
    """基础缓存服务类，使用Redis Hash结构实现基于标签的缓存管理"""

    def __init__(self, *args, **kwargs):
        self.redis = get_redis_sync()
        self.cache_prefix = "service:cache"
        self.default_expire = 3600  # 默认过期时间2小时
        self.trigger_extend_ttl_ratio = 0.2 # 触发延长过期时间比例
        super().__init__(*args, **kwargs)

    def _generate_cache_field(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """生成缓存字段名：函数名和参数的哈希值"""
        # 序列化参数，排除self参数
        filtered_args = args
        params_key = hashlib.md5(
            json.dumps({
                'args': filtered_args,
                'kwargs': kwargs
            }, sort_keys=True, default=str).encode('utf-8')
        ).hexdigest()

        return f"{func_name}:{params_key}"

    def _generate_cache_key(self, user_id: Optional[int], tag: str) -> str:
        """生成缓存key: prefix:tag:user_id 或 prefix:tag"""
        if user_id is not None:
            return f"{self.cache_prefix}:{tag}:{user_id}"
        return f"{self.cache_prefix}:{tag}"

    async def _expire_ttl(self, cache_key: str, cache_expire: int):
        ttl = await self.redis.ttl(cache_key)
        if ttl <= int(cache_expire * self.trigger_extend_ttl_ratio):
            # 如果缓存已过期，则更新过期时间
            await self.redis.expire(cache_key, cache_expire)
        return True

    @staticmethod
    def cache_result_by_tag(expire: Optional[int] = None, tag: Optional[str] = None):
        """根据tag缓存函数结果的装饰器

        Args:
            expire: 缓存过期时间（秒），默认使用default_expire
            tag: 缓存标签，用于后续清除缓存，如果为None则使用函数名作为标签
        """

        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            async def wrapper(self, *args, **kwargs):
                # 确保self是BaseCacheService的子类实例
                if not isinstance(self, BaseServiceCache):
                    return await func(self, *args, **kwargs)

                # 获取用户ID
                user_id = getattr(self, 'user_id', None)
                if user_id is None:
                    # 如果没有user_id，则尝试从user对象获取
                    user = getattr(self, 'user', None)
                    if user is not None:
                        user_id = getattr(user, 'id', None)

                # 确定缓存标签
                cache_tag = tag if tag is not None else func.__name__

                # 生成缓存key和字段
                cache_key = self._generate_cache_key(user_id, cache_tag)
                cache_field = self._generate_cache_field(func.__name__, args, kwargs)

                # 设置缓存参数
                cache_expire = expire if expire is not None else self.default_expire

                # 尝试从缓存获取结果
                try:
                    cached_result = await self.redis.hget(cache_key, cache_field)
                    if cached_result is not None:
                        await self._expire_ttl(cache_key, cache_expire)
                        return json.loads(cached_result)
                except Exception:
                    # 缓存读取失败，继续执行函数
                    pass

                # 执行函数获取结果
                result = await func(self, *args, **kwargs)

                # 缓存结果
                try:
                    await self.redis.hset(cache_key, cache_field, json.dumps(result, default=str))
                    # 设置整个hash的过期时间
                    await self.redis.expire(cache_key, cache_expire)
                except Exception:
                    # 缓存存储失败，不影响主流程
                    pass

                return result

            return wrapper

        return decorator

    @staticmethod
    def clear_cache_by_tags(tags: Optional[List[str]] = None):
        """根据tag清除缓存的装饰器

        Args:
            tags: 需要清除的缓存标签列表
                  如果不提供，则默认清除当前函数名对应的标签缓存
        """

        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            async def wrapper(self, *args, **kwargs):
                # 确保self是BaseCacheService的子类实例
                if not isinstance(self, BaseServiceCache):
                    return await func(self, *args, **kwargs)

                # 获取用户ID
                user_id = getattr(self, 'user_id', None)
                if user_id is None:
                    user = getattr(self, 'user', None)
                    if user is not None:
                        user_id = getattr(user, 'id', None)

                # 确定要清除的标签列表
                tags_to_clear = tags if tags is not None else [func.__name__]

                # 先执行函数
                result = await func(self, *args, **kwargs)

                if isinstance(result, tuple):
                    status = result[0]
                else:
                    status = result
                if status is not None:
                    # 函数执行成功清除缓存
                    try:
                        for tag in tags_to_clear:
                            cache_key = self._generate_cache_key(user_id, tag)
                            # 删除整个hash
                            await self.redis.delete(cache_key)
                    except Exception:
                        # 清除缓存失败不影响主流程
                        pass

                return result

            return wrapper

        return decorator

    async def manual_clear_cache_by_tags(self, user_id: Optional[int], tags: List[str]):
        """手动根据标签清除缓存

        Args:
            user_id: 用户ID，如果为None则清除不带用户ID的缓存
            tags: 需要清除的缓存标签列表
        """
        try:
            for tag in tags:
                cache_key = self._generate_cache_key(user_id, tag)
                # 删除整个hash
                await self.redis.delete(cache_key)
        except Exception:
            # 清除缓存失败不影响主流程
            pass

    @staticmethod
    def cache_result(expire: Optional[int] = None):
        """缓存函数结果的装饰器

        Args:
            expire: 缓存过期时间（秒），默认使用default_expire
            tag: 缓存标签，用于后续清除缓存，如果为None则使用函数名作为标签
        """

        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            async def wrapper(self, *args, **kwargs):
                # 确保self是BaseCacheService的子类实例
                if not isinstance(self, BaseServiceCache):
                    return await func(self, *args, **kwargs)

                # 获取用户ID
                user_id = getattr(self, 'user_id', None)
                if user_id is None:
                    # 如果没有user_id，则尝试从user对象获取
                    user = getattr(self, 'user', None)
                    if user is not None:
                        user_id = getattr(user, 'id', None)



                # 生成缓存key和字段
                cache_key = self._generate_cache_key(user_id, '')
                cache_field = self._generate_cache_field(func.__name__, args, kwargs)

                cache_key = f'{cache_key}:{cache_field}'
                # 设置缓存参数
                cache_expire = expire if expire is not None else self.default_expire

                # 尝试从缓存获取结果
                try:
                    cached_result = await self.redis.get(cache_key)
                    if cached_result is not None:
                        return json.loads(cached_result)
                except Exception:
                    # 缓存读取失败，继续执行函数
                    pass

                # 执行函数获取结果
                result = await func(self, *args, **kwargs)

                # 缓存结果
                try:
                    await self.redis.set(cache_key, json.dumps(result, default=str), expire=cache_expire)
                except Exception:
                    # 缓存存储失败，不影响主流程
                    pass

                return result

            return wrapper

        return decorator
