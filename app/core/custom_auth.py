import hashlib
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable
import json
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
import logging
from fastapi.responses import StreamingResponse
from starlette.responses import JSONResponse

from app.core.database import get_db_session
from app.core.redis import get_redis_sync
from app.models.user import User

logger = logging.getLogger(__name__)

USER_ATTR = "current_user"
SECRET_KEY = "your-secret-key-here"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 10080
MAX_DEVICES_PER_USER = 2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


def generate_device_fingerprint(request: Request) -> str:
    """生成唯一设备指纹"""
    user_agent = request.headers.get("User-Agent", "")
    ip = request.client.host or "0.0.0.0"
    return hashlib.sha256(f"{user_agent}:{ip}".encode()).hexdigest()


async def get_user_from_db(user_id: str) -> User:
    """
    根据用户ID从数据库获取用户信息
    :param user_id: 用户ID (字符串形式)
    :return: User 模型实例
    :raises HTTPException: 用户不存在时返回404错误
    """
    # 将字符串ID转换为整数（根据实际ID类型调整）
    try:
        user_id_int = int(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    # 获取数据库会话
    async with get_db_session() as session:
        stmt = select(User).where(User.id == user_id_int)
        result = await session.execute(stmt)

    user = result.scalars().first()

    # 检查用户是否存在
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"User with ID {user_id} not found")

    return user


async def get_current_user(request: Request):
    """通过JWT令牌获取已认证用户"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(401, "无效的认证凭证")
    token = auth_header.split(" ")[1]
    print("=" * 10)
    print(f"token: {token}")
    print("=" * 10)

    try:
        # 解码JWT令牌
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证凭证")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌验证失败")

    # 从数据库获取用户（示例使用模拟数据库）
    user = await get_user_from_db(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")

    return user

async def try_get_current_user(request: Request):
    """尝试通过JWT令牌获取已认证用户"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ")[1]
    try:
        # 解码JWT令牌
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            return None
    except JWTError:
        return None

    # 从数据库获取用户（示例使用模拟数据库）
    user = await get_user_from_db(user_id)
    if not user:
        return None
    # 记录用户接口行为
    await record_user_interface_behavior(request, user)
    return user


class DeviceManager:
    """设备管理服务"""

    def __init__(self):
        self.redis = get_redis_sync()

    async def add_device(
        self, user_id: str, device_id: str, max_devices: int = MAX_DEVICES_PER_USER
    ):
        """添加设备并处理设备限制"""
        key = f"user:{user_id}:devices"
        current_count = await self.redis.zcard(key)

        # 设备数超限时删除最早设备
        if current_count >= max_devices:
            oldest_devices = await self.redis.zrange(key, 0, 0)
            if oldest_devices:
                await self.redis.zrem(key, oldest_devices[0])

        # 添加新设备（使用当前时间戳作为score）
        await self.redis.zadd(key, {device_id: datetime.now().timestamp()})

    async def is_active(self, user_id: str, device_id: str) -> bool:
        """检查设备是否在活跃列表中"""
        key = f"user:{user_id}:devices"
        return await self.redis.zscore(key, device_id) is not None

    async def remove_device(self, user_id: str, device_id: str):
        """从活跃列表中删除设备"""
        key = f"user:{user_id}:devices"
        await self.redis.zrem(key, device_id)


def create_access_token(user_id: str, device_id: str) -> str:
    """创建绑定设备的JWT令牌"""
    payload = {
        "sub": str(user_id),
        "device_id": device_id,
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


async def verify_token(token: str = Depends(oauth2_scheme)) -> str:
    """验证JWT令牌并提取用户ID"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        device_id: str = payload.get("device_id")
        if not user_id or not device_id:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "无效令牌")

        # 检查设备是否在活跃列表中
        if not await DeviceManager().is_active(user_id, device_id):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "设备会话已失效")

        return user_id
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "令牌验证失败")


def auth_required(max_devices: int = MAX_DEVICES_PER_USER) -> Callable:
    """认证装饰器工厂函数"""

    def decorator(endpoint: Callable) -> Callable:
        @wraps(endpoint)
        async def wrapper(
            self,
            request: Request,
            # user_id: str = Depends(verify_token),  # 令牌验证
            *args,
            **kwargs,
        ) -> Any:
            # 生成设备指纹
            if not isinstance(request, Request):
                # 尝试从类实例中提取 Request
                if hasattr(self, "request"):
                    request = self.request
                else:
                    raise RuntimeError("Request object not found")
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "无效的认证凭证")
            token = auth_header.split(" ")[1]
            user_id = await verify_token(token)
            # 从数据库获取用户（示例使用模拟数据库）
            user = await get_user_from_db(user_id)
            if not user:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
            request.state.user = user
            device_id = generate_device_fingerprint(request)
            request.state.device_id = device_id
            # 添加/更新设备
            await DeviceManager().add_device(user_id, device_id, max_devices)
            result = await endpoint(self, request, *args, **kwargs)
            if result:
                if isinstance(result, JSONResponse):
                    response_content = json.loads(result.body)
                    if isinstance(response_content, dict) and str(response_content.get('code')) == '10000':
                        # 记录用户接口行为
                        await record_user_interface_behavior(request, user)
                elif isinstance(result, StreamingResponse):
                    await record_user_interface_behavior(request, user)
            return result

        return wrapper

    return decorator


async def record_user_interface_behavior(request: Request, user: User):
    if request.method in ('GET', 'POST', 'PUT', 'DELETE'):
        from app.tasks.tasks import store_user_interface_behavior_record
        try:
            ip = get_client_ip(request)
            request_data = await parse_request_data_to_json(request)
            store_user_interface_behavior_record.send(user.id, {
                'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
                'resource_type': request.method,
                'resource_id': request.url.path,
                'resource_content': request_data,
                'extra_info': {
                    'ip': ip,
                },
            })
        except Exception as ex:
            logger.error(f"解析请求参数错误: {ex}")
    return

def get_client_ip(request: Request) -> str:
    # 先拿 X-Forwarded-For，取第一个
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    # 降级到 X-Real-IP
    xri = request.headers.get("X-Real-IP")
    if xri:
        return xri
    # 最后兜底
    return request.client.host or "127.0.0.1"

async def parse_request_data_to_json(request: Request) -> str:
    """
    解析请求参数并统一转换为JSON格式字典
    支持 JSON body、form-data、url参数等多种形式
    """
    if request.method in ("POST", "PUT", "DELETE"):
        # 获取内容类型
        content_type = request.headers.get("content-type", "").lower()

        if "application/json" in content_type:
            # JSON body 数据
            try:
                result = await request.json()
            except json.JSONDecodeError:
                result = {}

        elif "multipart/form-data" in content_type:
            # form-data 表单数据
            form_data = await request.form()
            result = dict(form_data)

        elif "application/x-www-form-urlencoded" in content_type:
            # URL编码的表单数据
            form_data = await request.form()
            result = dict(form_data)

        else:
            # 默认尝试解析为 JSON
            try:
                result = await request.json()
            except json.JSONDecodeError:
                result = {}
        if not result:
            # 如果没有解析到数据，尝试从 URL 参数中获取
            result = dict(request.query_params)

    elif request.method in ["GET", "PATCH"]:
        # URL 查询参数
        result = dict(request.query_params)

    else:
        # 其他请求方法默认使用查询参数
        result = dict(request.query_params)
    if result is None:
        result = {}
    return json.dumps(result)